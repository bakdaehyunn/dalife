# DaLife 개인 맛집 학습 루프 개선 계획

## 구현 상태 (2026-10-24)

첫 번째 운영 마일스톤과 개인화 루프의 실행 기반은 구현 및 활성화되었다.

- 신정동·이태원 mobility zone, coverage 조회, zone 기반 추천
- collection run 신규성·중복·근거 연결 지표와 KST quota 경계
- 추천 노출, 지도 요청, 저장, 방문 예정·확인·건너뜀 이벤트 원장
- Telegram callback과 통합 life sender의 24시간 후 방문 확인 작업
- 이벤트에서 재생성 가능한 취향 snapshot과 개인화·반복 감점 랭킹
- 80/20 exploit/explore 선택 및 session별 selection mode 저장
- 과거 session 기반 offline evaluation과 collection report

현재 live profile의 행동 이벤트는 0건이므로 개인화 가중치는 중립값으로
fallback한다. 과거 collection run에는 신규 계측값이 없기 때문에 지표가 0으로
보이며, 다음 수집부터 실제 신규성·중복률이 누적된다. 자동 weight 최적화와
golden scenario 승격 차단은 최소 30개 session과 10개 강한 행동 신호가 쌓인
뒤의 다음 마일스톤이다.

Telegram의 지도 동작은 직접 URL 클릭을 관찰한다고 주장하지 않는다. 사용자가
`지도` callback을 누르면 `map_requested`를 저장하고 실제 Kakao URL을 별도
메시지로 보낸다. 방문 여부는 후속 질문의 명시적 응답만 기록한다.

## 1. 목표

DaLife의 맛집 기능을 단순한 지역 검색 결과 정리에서 다음과 같은 개인화
시스템으로 발전시킨다.

```text
행동 반경 정의
  -> 후보와 근거 수집
  -> 추천 노출
  -> 사용자 행동 관찰
  -> 방문과 만족도 확인
  -> 취향 프로필 갱신
  -> 다음 추천과 탐색 전략 개선
```

최종 목표는 인기 있는 식당을 많이 보여주는 것이 아니라, 사용자의 실제
이동 가능 범위와 상황 안에서 선택 가능성이 높고 근거가 충분한 후보를
다양하게 제안하는 것이다.

## 2. 현재 기준선

2026-10-24 로컬 SQLite 기준:

| 항목 | 신정동 | 이태원 | 합계 |
| --- | ---: | ---: | ---: |
| 장소 | 244 | 208 | 452 |
| 좌표 보유 장소 | 244 | 208 | 452 |
| 블로그 근거가 연결된 장소 | 143 | 165 | 308 |
| 수집된 근거 | 4,409 | 6,217 | 10,626 |
| 등록된 수집 질의 | 73 | 73 | 146 |

운영 상태:

- Kakao Local과 Naver Blog 수집기가 매일 03:00에 실행된다.
- 최근 launchd 실행은 정상 종료하고 공급자 실패가 없다.
- 광역 탐색, 음식 종류, 상황, 탐색 키워드, 개별 장소 근거 갱신 질의가
  SQLite query ledger에 저장된다.
- 장소 중 약 68%에 하나 이상의 블로그 근거가 연결되어 있다.
- 맛집 사용자 피드백 이벤트는 아직 실질적으로 쌓이지 않았다.

현재 수집기는 운영 가능한 기반이지만, 행동 반경은 행정동 문자열로만
표현되고 질의별 신규 발견량과 중복률을 측정하지 않는다. 따라서 개인화
모델을 만들기 전에 수집 품질과 관찰 데이터를 먼저 보강해야 한다.

## 3. 설계 원칙

1. **행동을 먼저 기록한다.** 명시적 좋아요만이 아니라 노출, 지도 열기,
   저장, 방문, 재방문, 숨김을 모두 관찰 가능하게 만든다.
2. **수집량과 품질을 분리한다.** API 결과 수가 많아도 신규 장소나 유효한
   근거가 없으면 좋은 질의로 평가하지 않는다.
3. **거리보다 이동 비용을 사용한다.** 직선거리와 함께 도보, 대중교통,
   택시 기준의 허용 시간을 개인 취향으로 저장한다.
4. **설명 가능한 점수부터 시작한다.** 충분한 행동 데이터가 쌓이기 전에는
   가중치 기반 랭커를 사용하고 점수 근거를 저장한다.
5. **탐색을 보존한다.** 이미 선호하는 식당만 반복하지 않도록 일부 슬롯은
   신규 음식, 신규 동네, 불확실한 후보에 할당한다.
6. **SQLite를 source of truth로 유지한다.** 학습 프로필과 평가 지표도 원본
   이벤트에서 다시 만들 수 있는 파생 데이터로 취급한다.

## 4. 단계별 실행 계획

### Brick 1. 행동 반경 모델

#### 목적

`신정동`, `이태원` 같은 문자열을 실제 이동 가능한 생활권으로 바꾼다.

#### 구현

- `mobility_zones` 테이블을 추가한다.
  - `id`, `name`, `kind`, `center_latitude`, `center_longitude`
  - `walk_minutes`, `transit_minutes`, `taxi_minutes`
  - `active_weekdays`, `active_time_windows`, `priority`
- `mobility_zone_areas`로 기존 area와 zone의 관계를 저장한다.
- 장소에 zone 포함 여부와 중심점까지의 직선거리를 계산해 저장하거나
  조회 시 파생한다.
- 초기 zone은 수동 설정으로 시작한다.
  - 집 근처 도보 생활권
  - 집 기준 확장 생활권
  - 이태원·한남 활동 생활권
  - 자주 이용하는 역과 이동 경로
- CLI를 추가한다.
  - `dalife food zones list`
  - `dalife food zones add/update/disable`
  - `dalife food coverage --zone <zone>`

#### 완료 조건

- 모든 활성 장소가 하나 이상의 zone에 포함되거나 `outside_zone`으로
  명시된다.
- 추천 요청에서 area 문자열 대신 zone을 선택할 수 있다.
- 기존 신정동·이태원 추천 결과가 데이터 손실 없이 유지된다.

#### 검증

- zone 경계와 거리 계산 단위 테스트
- 기존 area 데이터 마이그레이션 테스트
- zone별 장소 수와 근거 연결률 CLI 테스트

### Brick 2. 수집 품질 계측

#### 목적

질의가 API 결과를 반환했는지가 아니라 데이터베이스를 얼마나 개선했는지
측정한다.

#### 구현

- `query_ledger_runs`에 다음 측정값을 추가한다.
  - `new_places_count`
  - `refreshed_places_count`
  - `new_evidence_count`
  - `duplicate_evidence_count`
  - `new_links_count`
  - `high_quality_links_count`
  - `unmatched_evidence_count`
- 다음 지표를 계산한다.
  - `novelty_rate = new_places / returned_places`
  - `evidence_match_rate = new_links / new_evidence`
  - `duplicate_rate = duplicates / returned_items`
  - `query_utility_score`
- local-date quota 계산을 `Asia/Seoul` 기준으로 통일한다. 현재 03:00 KST
  실행이 전날 UTC 사용량으로 표시되는 문제를 수정한다.
- 최근 효용이 낮은 질의는 실행 간격을 늘리고, 효용이 높은 facet과 zone에는
  예산을 더 배분한다.
- 0건 exact-place 질의는 일정 횟수 후 비활성화하거나 이름 정규화 검토 큐로
  이동한다.

#### 완료 조건

- 모든 신규 collection run에 품질 지표가 기록된다.
- `dalife food collection-report --days 30`에서 zone, provider, facet별 효용을
  비교할 수 있다.
- 중복률이 높은 질의와 장기 0건 질의를 자동 식별한다.
- KST 날짜별 quota 출력과 실제 03:00 실행 기록이 일치한다.

#### 검증

- 동일 응답 재수집 시 신규 건수가 0이 되는 idempotency 테스트
- KST 자정 경계 quota 테스트
- 질의 감속·비활성화 정책 테스트

### Brick 3. 추천 관찰 원장

#### 목적

무엇을 추천했는지뿐 아니라 사용자가 그 추천 이후 무엇을 했는지 기록한다.

#### 이벤트

- `recommendation_shown`
- `map_requested`
- `evidence_requested`
- `saved`
- `liked`
- `disliked`
- `hidden`
- `visit_planned`
- `visit_confirmed`
- `visit_skipped`
- `revisited`
- `rating_submitted`

#### 공통 컨텍스트

- recommendation session과 place ID
- 노출 순위와 당시 점수 breakdown
- zone과 예상 이동 비용
- 요청 시각, 요일, 식사 시간대
- 혼밥, 데이트, 가족 외식, 술자리 등 occasion
- 동행 유형
- 추천 당시 evidence tier와 사용한 근거
- 사용자 행동 시각과 선택 사유

#### 구현

- 범용 `user_feedback`를 append-only 관찰 원장으로 확장하거나 별도
  `recommendation_events` 테이블을 추가한다.
- Telegram 지도·블로그 링크를 추적 가능한 callback/button 흐름으로 바꾼다.
- 추천 후 일정 시간이 지나면 방문 여부를 한 번만 확인한다.
- 빠른 피드백 버튼과 상세 피드백을 분리한다.
- 같은 callback의 중복 처리는 idempotent하게 만든다.

#### 완료 조건

- 모든 추천 노출이 session과 candidate에 연결된다.
- 지도 열기, 저장, 숨김, 방문 확인을 Telegram에서 기록할 수 있다.
- 이벤트 원장만으로 장소별 funnel을 재구성할 수 있다.
- 추천되지 않은 장소의 자발적 방문도 기록할 수 있다.

#### 검증

- Telegram callback과 이벤트 idempotency 테스트
- session-candidate-event 참조 무결성 테스트
- 방문 확인 알림 중복 방지 테스트

### Brick 4. 설명 가능한 개인 취향 프로필

#### 목적

원본 이벤트에서 다시 계산할 수 있는 개인 취향 요약을 만든다.

#### 프로필 축

- 음식 종류와 메뉴
- 가격대
- 혼밥·모임·데이트·술자리 적합도
- 평일·주말 및 시간대
- zone별 이동 허용 시간
- 신규 장소 선호도와 익숙한 장소 선호도
- 예약·웨이팅 허용 성향
- 재방문 성향
- 근거 신뢰 성향

#### 구현

- `preference_features`와 `preference_snapshots`를 추가한다.
- 이벤트별 신호 강도를 명시한다.
  - 방문 후 높은 평점은 강한 양의 신호
  - 지도 열기는 약한 양의 신호
  - 노출 후 무반응은 즉시 부정 신호로 해석하지 않음
  - 숨김과 명시적 비선호는 강한 음의 신호
- 최근 행동에 더 큰 가중치를 주되 장기 취향도 보존한다.
- `dalife food profile show/rebuild/explain`을 제공한다.

#### 완료 조건

- 프로필을 언제든 이벤트 원장에서 동일하게 재생성할 수 있다.
- 각 선호 점수가 어떤 이벤트에서 만들어졌는지 추적할 수 있다.
- 데이터가 부족한 feature는 확신도가 낮다고 표시한다.

#### 검증

- 이벤트 조합별 feature 계산 테스트
- 시간 감쇠와 상충 피드백 테스트
- snapshot 재생성 결정성 테스트

### Brick 5. 개인화 재랭커

#### 목적

기존 장소 품질 점수에 개인 적합도와 상황 적합도를 결합한다.

#### 초기 점수 모델

```text
final_score =
    evidence_quality
  + place_quality
  + preference_fit
  + context_fit
  + mobility_fit
  + diversity_bonus
  + exploration_bonus
  - stale_penalty
  - repetition_penalty
  - explicit_negative_penalty
```

각 항목은 `score_breakdown_json`에 저장한다. 학습 모델을 사용하더라도 이
breakdown 계약은 유지한다.

#### 구현

- candidate generation과 ranking을 분리한다.
- hard filter는 영업 가능성, zone, 명시적 숨김, 잘못된 장소에만 사용한다.
- 근거가 약한 후보는 완전히 삭제하지 않고 discovery 슬롯에서 제한적으로
  노출한다.
- 최근 반복 노출된 장소에 감점한다.
- 상위 결과가 한 종류의 음식이나 한 골목에 몰리지 않도록 diversity
  constraint를 적용한다.

#### 완료 조건

- 동일 요청에 대해 기본 랭킹과 개인화 랭킹을 비교할 수 있다.
- 모든 추천에 상위 3개 점수 이유가 저장된다.
- 명시적 비선호와 이동 제한이 다음 추천에 반영된다.

#### 검증

- 고정 fixture를 사용한 랭킹 회귀 테스트
- 다양성, 반복 감점, negative feedback 테스트
- 기존 공개 CLI 결과 형식 회귀 테스트

### Brick 6. 탐색과 학습 정책

#### 목적

이미 아는 취향에 갇히지 않으면서도 추천 품질을 유지한다.

#### 구현

- 기본 슬롯 정책을 `80% exploit / 20% explore`로 시작한다.
- 탐색 유형을 구분한다.
  - 익숙한 음식의 신규 장소
  - 인접 음식 종류
  - 새로운 zone
  - 근거는 좋지만 개인 데이터가 없는 후보
- 사용자가 탐색 강도를 조절할 수 있게 한다.
- 탐색 후보의 성과를 일반 후보와 별도로 측정한다.

#### 완료 조건

- 추천 세션마다 exploit/explore 출처가 기록된다.
- 동일 장소 반복률이 목표 한도 이하로 유지된다.
- 탐색 후보의 선택·방문 전환율을 확인할 수 있다.

### Brick 7. 오프라인 평가와 운영 대시보드

#### 목적

추천이 실제로 좋아지는지 배포 전에 검증한다.

#### 평가 데이터

- 과거 추천 session과 당시 candidate snapshot
- 이후 발생한 사용자 이벤트
- 사용자 지정 golden scenarios
  - 평일 혼밥
  - 금요일 저녁 술자리
  - 가족 외식
  - 가까운 곳 우선
  - 새로운 곳 탐색

#### 지표

- `precision@k`에 대응하는 선택·저장·방문 비율
- `MRR` 또는 첫 선택 순위
- 방문 전환율과 재방문율
- 명시적 비선호 노출률
- 추천 내 음식·가격·zone 다양성
- 반복 노출률
- 근거 커버리지와 freshness
- 탐색 후보 성공률

#### 완료 조건

- 랭킹 변경 전후를 같은 snapshot으로 비교한다.
- 최소 golden scenario가 모두 자동 평가된다.
- 지표가 악화되면 새 weight 설정을 활성화하지 않는다.

## 5. 권장 구현 순서

| 순서 | 작업 | 이유 |
| --- | --- | --- |
| 1 | 행동 반경 모델 | 수집과 추천의 공간 경계를 먼저 고정해야 함 |
| 2 | 수집 품질 계측 및 KST quota 수정 | 현재 데이터가 실제로 개선되는지 판단해야 함 |
| 3 | 추천 관찰 원장 | 개인화에 필요한 학습 신호 확보 |
| 4 | 개인 취향 프로필 | 원본 행동을 설명 가능한 feature로 변환 |
| 5 | 개인화 재랭커 | 충분한 데이터가 생긴 뒤 순위에 반영 |
| 6 | 탐색 정책 | 편향과 반복 추천 방지 |
| 7 | 평가·운영 대시보드 | 변경 효과 검증과 지속 운영 |

Brick 1과 Brick 2는 서로 밀접하지만 한 번에 구현하지 않는다. 먼저 zone
schema와 조회를 완성하고, 그 다음 collection run 계측을 추가한다. Brick 3은
프로필 계산 없이 이벤트 저장만 먼저 배포해 데이터가 쌓일 시간을 확보한다.

## 6. 첫 번째 마일스톤

첫 마일스톤은 **개인화 모델 구현이 아니라 측정 가능한 데이터 기반 완성**이다.

포함 범위:

1. `mobility_zones`와 기존 area 연결
2. zone별 coverage 명령
3. collection run의 신규·중복·연결 품질 지표
4. KST quota 날짜 수정
5. 저효용 질의 보고서
6. `recommendation_shown`, `map_requested`, `saved`, `hidden`, `visit_confirmed`
   이벤트 저장

성공 기준:

- 모든 추천 후보가 zone과 이동 거리 정보를 가진다.
- 최근 30일 수집에서 어떤 질의가 신규 장소를 만들었는지 확인할 수 있다.
- 추천 노출부터 방문 확인까지 최소 funnel을 SQLite로 재구성할 수 있다.
- 최소 30개의 실제 추천 session과 10개 이상의 방문·비선호 강한 신호가
  쌓이기 전에는 자동 weight 학습을 시작하지 않는다.

## 7. 범위 밖

초기 단계에서는 다음을 구현하지 않는다.

- 별도 그래프 데이터베이스 도입
- 벡터 데이터베이스 추가
- 외부 ML 학습 플랫폼
- 사용자 행동을 근거 없이 추론하는 자동 라벨링
- Instagram·Threads 비공식 자동 수집
- 설명할 수 없는 end-to-end 추천 모델

현재 SQLite와 명시적 Telegram 상호작용만으로 먼저 충분한 학습 신호를
확보한다. 새로운 저장 기술은 데이터 규모나 질의 요구가 SQLite의 한계를
실제로 넘을 때 검토한다.

## 8. 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| 클릭을 선호로 과대 해석 | 행동별 신호 강도와 confidence 분리 |
| 추천하지 않은 장소 방문 누락 | 자발적 방문 기록 명령 제공 |
| 블로그 중복과 광고성 근거 | 중복률, 저자 반복, 최신성, 이름·지역 일치 점수 기록 |
| 익숙한 음식만 반복 | exploration 슬롯과 category diversity 제한 |
| 데이터 부족 상태에서 과적합 | 최소 이벤트 기준 전에는 rule-based profile 유지 |
| 이동 반경이 상황마다 달라짐 | zone에 시간대·요일·이동수단 조건 저장 |
| API quota 날짜 혼선 | 모든 원장은 UTC 저장, 운영 집계는 명시적 KST 경계 사용 |

## 9. 완료 정의

개인 맛집 학습 루프는 다음 조건을 모두 만족할 때 완료로 본다.

- 추천의 입력, 후보, 점수, 노출, 행동, 방문 결과가 하나의 감사 가능한
  흐름으로 연결된다.
- 취향 프로필을 원본 이벤트에서 재생성할 수 있다.
- 추천마다 개인화 이유와 탐색 이유를 설명할 수 있다.
- 신규 랭킹을 과거 snapshot과 golden scenario로 평가할 수 있다.
- 사용자 반응이 다음 추천에 자동으로 반영된다.
- 수집기가 신규성과 근거 품질에 따라 query budget을 조정한다.
- 행동 데이터가 부족할 때는 일반 품질 랭킹으로 안전하게 fallback한다.
