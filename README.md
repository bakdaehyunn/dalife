# 다카이브봇

다카이브봇은 내가 흥미롭게 본 글과 캡처를 Telegram으로 공유하면, 아이디어 주머니로 다시 꺼내 쓸 수 있게 정리해 주는 로컬 봇입니다.
현재 통합 브랜치에서는 Momukbot의 맛집 추천 도메인과 Honsanam Reminder의 생활 알림 도메인을 다카이브봇 안으로 흡수해, 아카이브, 맛집, 생활 루틴, 개인 코스를 하나의 SQLite 기반 개인 컨텍스트 플랫폼으로 묶는 방향으로 확장하고 있습니다.

웹에서 본 글, 소셜 피드 캡처, 다시 생각해 보고 싶은 문장을 Telegram으로 보내면 원본은 내 컴퓨터에 저장되고, 내용은 관심사별 아카이브 항목으로 정리됩니다. 단순히 파일을 모아두는 것이 아니라, 캡처 속 내용을 읽어 나중에 아이디어로 꺼내 쓸 수 있는 형태로 남깁니다.

## 이 프로젝트의 강점

- Telegram 공유 채팅방에 보내기만 하면 돼서 저장 과정이 빠릅니다.
- 원본 메시지와 첨부 파일을 로컬에 저장해 외부 서비스에만 의존하지 않습니다.
- 스크린샷을 이미지 파일로만 보지 않고, 안에 담긴 글의 핵심 내용까지 정리합니다.
- AI, 커리어, 테크놀로지, 스포츠 같은 관심사와 세부 주제로 분류합니다.
- 왜 저장했는지, 다시 볼 우선순위가 무엇인지, 나중에 어떤 생각과 연결될 수 있는지까지 남깁니다.
- 정리된 항목 중 판단이 필요한 것만 Telegram 카드로 다시 알려주고, 버튼 선택을 SQLite에 감사 기록으로 남깁니다.
- 맛집 후보, 외부 근거, 생활 알림, 코스 제안 같은 개인 도메인 데이터도 같은 로컬 SQLite 경계 안에 저장하도록 확장 중입니다.

## 어떤 프로젝트인가

다카이브봇은 흘러가는 캡처와 글을 아이디어 주머니에 담아두는 개인용 아카이브 시스템입니다. 공유와 전달은 Telegram 채팅방에서 하고, 저장은 로컬 폴더와 SQLite, 정리는 Codex 기반 processor가 맡습니다.

프로젝트의 중심은 스크린샷입니다. 링크나 북마크처럼 주소만 남기는 것이 아니라, 실제로 캡처 안에 들어 있는 내용과 맥락을 읽어 제목, 요약, 주요 포인트, 관심사, 다시 볼 이유로 정리합니다. 시간이 지나면 흩어진 캡처들이 관심사별 아카이브가 되고, 이후에는 서로 관련된 캡처와 반복되는 주제를 찾아 인사이트로 발전시킬 수 있습니다.

장기적으로 다카이브봇이 향하는 최종 제품 레이어는 Viewpoint Layer입니다. 저장된 캡처를 단순히 다시 찾는 데서 끝내지 않고, 내가 반복해서 보는 주제, 계속 남는 질문, 서로 이어지는 캡처, 프로젝트나 글감으로 발전할 수 있는 생각을 Codex와 다시 논의할 수 있는 재료로 만드는 방향입니다.

## 아카이브가 쌓이는 과정

1. Telegram에서 다카이브봇과 1:1 채팅을 엽니다.
2. 나중에 다시 보고 싶은 캡처나 사진을 보냅니다.
3. 다카이브봇이 원본 메시지와 파일을 로컬에 저장합니다.
4. 예약된 processor가 새 항목만 골라 핵심 내용과 관심사 분류를 정리합니다.
5. 유용한 선택이 있을 때만 Telegram 카드가 오고, `Project seed`, `Revisit`, `Keep`, `Needs review`, `Ignore` 같은 버튼을 눌러 다음 상태를 남깁니다.

## 어떻게 작동하나

다카이브봇은 세 단계로 움직입니다.

첫 번째는 수집입니다. Telegram poller가 허용된 채팅에서 새 메시지를 확인하고, 텍스트와 캡션, 사진, 문서를 로컬 SQLite DB와 `.local/captures/` 폴더에 저장합니다. Telegram에만 의존하지 않도록 원본 파일도 로컬에 내려받습니다.

두 번째는 정리입니다. 예약된 processor가 주기적으로 SQLite에서 아직 정리되지 않은 항목만 찾습니다. 처리할 항목이 없으면 아무 작업 없이 종료하고, 처리할 항목이 있으면 Codex가 캡처와 이미지 내용을 읽어 구조화된 JSON을 반환합니다. Python 코드는 그 JSON을 검증한 뒤 SQLite에 저장하고, 정상 처리된 항목이 있으면 `.local/graph/semantic-store/` RDF 그래프를 새로 만들고 `.local/graph/darchivebot.jsonld`에는 가볍게 볼 수 있는 JSON-LD export를 남깁니다. 실패한 항목은 바로 무한 재시도하지 않고 retry/backoff 상태로 남기며, 반복 실패하면 `failed_blocked`로 멈춥니다. Codex는 DB나 그래프 파일을 직접 수정하지 않습니다.

세 번째는 추천입니다. 정리 결과가 낮은 신뢰도, 프로젝트 씨앗, 재방문 후보, 주간 인사이트 후보처럼 사용자의 선택이 필요한 경우에만 Telegram으로 짧은 카드와 버튼을 보냅니다. 전체 원문이나 개인 파일을 Telegram으로 다시 보내지 않고, 제목/짧은 요약/추천 이유만 보냅니다. 버튼 선택은 `bot_prompts`와 `bot_prompt_events`에 저장되어 나중에 어떤 판단을 했는지 추적할 수 있습니다.

이 구조 덕분에 다카이브봇은 조용히 돌아가면서도 원본 보관, 관심사 분류, 요약, 나중에 다시 볼 이유, 관심사 그래프, 사용자의 선택 기록을 분리해서 남길 수 있습니다.

전체 레이어는 다음처럼 쌓입니다.

```text
Capture Layer
  -> Telegram으로 받은 원본 메시지와 파일

Archive Layer
  -> SQLite에 저장된 캡처, 파일, 정리 결과, 처리 상태

Search Layer
  -> SQLite FTS5로 만든 로컬 검색 색인, 리뷰 큐, 재방문 큐, 로컬 웹 UI

Telegram Recommendation Layer
  -> 정리 후 필요한 선택만 보내는 짧은 카드, inline button, 선택 감사 기록

Semantic Graph Layer
  -> 관심사, 주제, 개념, 주장, 질문, 연결 후보

Viewpoint Layer
  -> 관련 캡처, 반복되는 테마, 남아 있는 질문, 프로젝트 씨앗, Codex 논의 맥락
```

## 개인 컨텍스트 플랫폼 방향

다카이브봇은 이제 세 개의 독립 도구를 한 번에 지우는 방식이 아니라, 동작을 보존하면서 하나의 canonical repo로 옮기는 방식으로 통합됩니다.

- `archive`: 기존 다카이브 캡처, 처리, 검색, 리뷰, graph/export 흐름입니다.
- `food`: Momukbot에서 온 맛집 수집, 근거 저장, 랭킹, 개인 피드백 도메인입니다.
- `life`: Honsanam Reminder에서 온 생활 루틴, 알림 스케줄, 확인 상태 도메인입니다.
- `course`: 저장된 맛집, 생활 루틴, 아카이브 관심사를 조합하는 개인 코스 도메인입니다.

SQLite가 운영 데이터의 source of truth이고, RDF graph와 JSON-LD export는 검증된 SQLite row에서 다시 만들 수 있는 파생물입니다. 기존 `momuk`과 `honsanam-reminder` CLI는 native 이관이 끝날 때까지 Darchivebot console script wrapper로 유지됩니다.

## 로컬 아카이브에 정리되는 내용

다카이브봇은 Telegram으로 보낸 캡처와 메시지를 로컬 폴더와 SQLite DB에 저장하고, 나중에 찾아보기 쉬운 형태로 정리합니다.

- 원본 메시지와 첨부 파일은 로컬에 보관합니다.
- 제목과 핵심 요약으로 목록에서 빠르게 알아볼 수 있게 합니다.
- AI, 커리어, 테크놀로지, 스포츠 같은 관심사와 세부 주제로 분류합니다.
- 주요 포인트와 원문 텍스트를 함께 남겨 다시 읽기 쉽게 합니다.
- 저장 이유, 다시 볼 우선순위, 태그를 붙여 나중에 검색하거나 분류할 수 있게 합니다.
- 나중에 다른 캡처와 연결될 수 있는 작은 insight seed, 질문, relation candidate를 남깁니다.
- 검증된 정리 결과를 로컬 RDF 관심사 그래프에 저장해 관계를 읽고 질의할 수 있게 준비합니다.
- 처리할 새 항목이 없으면 scheduled processor는 조용히 종료합니다.
- 사용자의 판단이 필요한 항목만 Telegram prompt로 보내고, 버튼 선택을 로컬 SQLite에 남깁니다.

## 빠른 시작

```bash
cd /Users/hennei/workspace/darchivebot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
darchive init
darchive doctor
```

개인 아카이브 용도는 Telegram 그룹보다 봇과의 1:1 채팅을 권장합니다. 설정이 단순하고, 다른 대화와 섞이지 않아 캡처함으로 쓰기 좋습니다.

`.env`에 Telegram token과 허용 채팅방을 넣습니다. token, chat id, admin user id는 출력하거나 커밋하지 않습니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_ADMIN_USER_IDS=
DARCHIVE_ALLOW_ALL_CHATS=false
```

테스트된 설정 흐름:

```bash
darchive setup --non-interactive \
  --telegram-bot-token '<BOT_TOKEN>' \
  --telegram-chat-id '<CHAT_ID>' \
  --telegram-admin-user-id '<YOUR_USER_ID>'
darchive doctor --online
darchive telegram-commands sync
darchive send-test --allowed
```

같은 setup 명령에서 `--kakao-rest-api-key`, `--naver-client-id`,
`--naver-client-secret`도 설정할 수 있습니다. 호환 wrapper는 기존
`--telegram-allowed-chat-ids`, `--telegram-admin-user-ids` 이름도 허용합니다.

일반 운영은 launchd/cron이 poller, processor, digest prompt를 관리하는 방식입니다.

```bash
scripts/install_launch_agent.sh
```

직접 실행하는 명령은 테스트/디버그용입니다. 평소에는 Telegram에 저장하고, 필요할 때 오는 카드의 버튼을 누르는 흐름이 기본입니다. 캡처 동작을 확인할 때만 한 터미널에서 capture poller를 켜 둡니다.

```bash
darchive telegram
darchive telegram-digest --kind revisit --dry-run
```

다른 터미널에서 처리 계획과 상태를 확인할 수 있지만, 일반 사용 흐름에 필수는 아닙니다.

```bash
darchive list
darchive pending
darchive process
darchive search "검색어"
darchive review
darchive web
```

## 주요 명령어

```bash
darchive init
darchive setup
darchive doctor
darchive doctor --online
darchive discover-chat
darchive rooms
darchive telegram-commands show
darchive telegram-commands sync
darchive telegram
darchive pending
darchive process
darchive process --export-graph
darchive telegram-digest
darchive telegram-digest --kind project-seed
darchive telegram-digest --kind weekly
darchive reprocess-plan
darchive reprocess-plan --json
darchive reprocess --capture-id <capture-id> --dry-run
darchive reprocess --capture-id <capture-id>
darchive archive list
darchive archive search <query>
darchive archive review
darchive archive show <capture-id>
darchive food parse "오목교역 곱창 맛집 추천"
darchive food plan-collection --area 신정동 --daily-quota-limit 30
darchive food due-queries
darchive food import-provider-config --source-env /path/to/momukbot/.env --dry-run
darchive food import-momuk-history --root /path/to/momukbot --dry-run
darchive food plan-history-refresh --area 신정동 --legacy-area "현재 위치" --persist
darchive food quota --json
darchive food run-collection --max-queries 20 --max-quota-cost 20 --dry-run
darchive food recommend-local --area 신정동 --topic "고기 저녁" --count 10
darchive life list
darchive life next --date 2026-08-29 --days 7
darchive life preview --date 2026-08-29 --time 09:00
darchive life import-honsanam --root /path/to/honsanam-reminder-bot --dry-run
darchive life run-once --dry-run --json
darchive life show trash --json
darchive life add custom --id water-plants --title "화분 물주기" --kind weekly --time 09:30 --weekday sun --action "화분에 물 주기"
darchive life pending --json
darchive life pattern show
darchive course plan --area 이태원 --date 2026-08-29 --time 18:30
darchive schedule plan
darchive schedule cutover-check
python -m darchivebot.launchd write . --include-life-sender
darchive graph init
darchive graph sync
darchive graph store-export
darchive graph export
darchive graph stats
darchive graph quality
darchive search <query>
darchive search <query> --rebuild
darchive review
darchive review --needs-review
darchive review --revisit
darchive web
darchive interests
darchive concepts
darchive related <capture-id>
darchive insights
darchive insights generate --period weekly --dry-run
darchive insights generate --period weekly
darchive insights show <insight-id>
darchive process --no-codex
darchive list
darchive show <capture-id>
darchive send-test --chat-id <telegram-chat-id>
```

- `telegram`: Telegram에서 보낸 글, 캡처, 사진, 문서를 로컬에 저장합니다.
- `pending`: 아직 정리되지 않은 항목과 처리 계획을 미리 봅니다.
- `process`: 새 항목이 있을 때만 내용을 정리하고 로컬 DB에 저장합니다.
- `process --export-graph`: 새 항목이 정리되면 RDF semantic store와 lightweight JSON-LD export를 함께 새로 만듭니다.
- `telegram-digest`: 재방문, 프로젝트 씨앗, 주간 인사이트 후보를 짧은 Telegram 버튼 카드로 보냅니다. 예약 실행용이며, 일반 사용자가 직접 명령을 외워 쓸 필요는 없습니다.
- `telegram-digest --dry-run --json`: 실제 Telegram 메시지를 보내지 않고 어떤 카드가 만들어질지 로컬에서 확인합니다.
- `archive ...`: 기존 archive 관련 flat command의 grouped alias입니다. `darchive list`와 `darchive archive list`는 같은 로컬 archive 데이터를 봅니다.
- `food parse`: 맛집 요청의 지역, 음식 주제, 인원 수, 현재 위치 필요 여부를 provider 호출 없이 파싱합니다.
- `food plan-collection`: 한도 안에서 지역, 키워드, provider, 정렬 방식을 분산한 맛집 수집 query plan을 만듭니다.
- `food due-queries`: SQLite query ledger에서 실행할 차례가 된 food collection query를 확인합니다.
- `food import-provider-config`: 기존 Momukbot `.env`에서 Kakao/Naver 설정만 가져오며 기존 Darchive 설정과 secret 출력은 건드리지 않습니다.
- `food import-momuk-history`: 기존 추천 row를 request session과 candidate로 idempotent하게 가져옵니다. raw model response는 복사하지 않으며 기존 place 이름이 유일하게 일치할 때만 연결합니다.
- `food plan-history-refresh`: 명시한 legacy area의 반복 후보만 exact-place Kakao/Naver refresh query로 변환합니다. 다른 지역 history는 자동으로 섞지 않습니다.
- `food quota`: immutable query execution log를 기준으로 provider별 당일 사용량과 남은 soft limit을 표시합니다.
- `food run-collection`: provider별 일일 soft limit와 실행당 quota cap 안에서 due query를 분산 실행하고 모든 장소/근거를 SQLite에 저장합니다.
- `food recommend-local`: 검증되어 SQLite에 저장된 장소와 근거, 개인 feedback만으로 추천을 랭킹하고 추천 session을 기록합니다.
- `DARCHIVE_NATIVE_PERSONAL_TELEGRAM=true`: Telegram 맛집, 생활 알림 조회, 코스 요청을 archive capture 대신 SQLite 기반 native handler로 처리하고, 맛집 상위 후보의 좋아요/별로/방문/숨김/비슷한 곳 feedback 버튼을 활성화합니다. 기본값은 `false`이며 검증된 방에서 전환하기 전까지 기존 capture 동작을 유지합니다.
- `DARCHIVE_LIFE_TIMEZONE=Asia/Seoul`: 생활 알림의 현재 시각과 CLI 입력 시각을 해석할 timezone입니다. 기존 동작과의 호환을 위해 기본값은 `Asia/Seoul`입니다.
- `life list`: Honsanam 기본 루틴에서 이관한 알림 정의를 확인합니다.
- `life next`: 지정한 날짜부터 며칠 안에 예정된 기본 생활 알림을 확인합니다.
- `life preview`: Honsanam 기본 루틴 기준으로 특정 KST 시각에 어떤 알림이 due인지 확인합니다.
- `life import-honsanam`: 기존 Honsanam 설정, 발송 이력, interaction, confirmation JSON을 shared SQLite로 idempotent하게 가져옵니다. 실제 import 전에 `--dry-run`으로 확인할 수 있습니다.
- `life run-once`: SQLite에 저장된 고정/사용자 정의 일정과 발송 상태를 기준으로 due 알림을 Telegram에 한 번만 보냅니다. `--dry-run`은 메시지나 reminder event를 만들지 않습니다. 기존 Honsanam job과 중복 실행되지 않도록 통합 launchd 전환 전에는 수동 검증에만 사용합니다.
- `course plan`: 저장된 archive metadata, food ranking, due life event를 SQLite에서 읽어 개인 코스 초안을 만들고 `--persist`로 근거 연결을 저장합니다.
- `schedule plan`: Telegram polling, archive processing, digest, food/life 계획을 포함한 unified scheduler plan을 확인합니다.
- `schedule cutover-check`: launchd 상태, native Telegram gate, life sender 관리 상태, SQLite confirmation backlog를 읽기 전용으로 검사합니다. blocker가 있으면 종료 코드 1을 반환하며 agent를 load/unload하지 않습니다.
- `search`: SQLite FTS5 로컬 색인으로 저장된 아카이브를 검색하고 어떤 필드가 매칭됐는지 보여줍니다.
- `search --rebuild`: 검증된 archive row에서 검색 색인을 결정적으로 다시 만듭니다.
- `review`: 다시 확인하거나 나중에 꺼내볼 아카이브 항목을 로컬 큐로 보여줍니다.
- `review --needs-review`: Codex 정리 신뢰도가 낮거나 사람이 확인해야 하는 항목만 봅니다.
- `review --revisit`: 재방문 우선순위, 재방문 이유, insight seed가 있는 항목을 봅니다.
- `web`: `127.0.0.1`에만 바인딩되는 로컬 웹 UI를 열어 목록, 검색, 리뷰, 상세, 관련 항목, insight note를 확인합니다.
- `reprocess-plan`: 이미 정리된 항목 중 분류가 약하거나 fallback으로 처리된 항목을 찾아, 왜 다시 정리할 후보인지 보여줍니다.
- `reprocess-plan --json`: 후보 목록을 자동화나 점검에 쓰기 좋은 JSON으로 출력합니다.
- `reprocess --capture-id <capture-id> --dry-run`: 선택한 항목을 다시 정리한다면 무엇을 대상으로 할지 미리 봅니다. SQLite row는 바꾸지 않습니다.
- `reprocess --capture-id <capture-id>`: 명시한 캡처 하나만 다시 정리하고, 성공하면 현재 archive row를 갱신하고 semantic graph store와 JSON-LD export를 함께 새로 만듭니다. 이전 정리 결과는 archive interpretation history로 남고, 실패해도 기존 archive row와 처리 완료 상태는 유지합니다.
- `graph init`: `.local/graph/semantic-store/`에 로컬 RDF 그래프 store를 준비합니다.
- `graph sync`: SQLite의 검증된 archive row에서 RDF semantic store를 다시 만듭니다.
- `graph sync --include-raw-text`: semantic store에 원문 전체까지 포함합니다. 로컬 분석 목적일 때만 사용합니다.
- `graph store-export`: semantic store를 `.local/graph/semantic-store.nq` N-Quads 파일로 내보냅니다.
- `graph export`: 정리된 아카이브 항목을 `.local/graph/darchivebot.jsonld`에 lightweight JSON-LD export로 내보냅니다. 전체 semantic store 백업이 아니라 사람이 확인하기 쉬운 휴대용 export입니다. 기본값은 원문 전체를 내보내지 않습니다.
- `graph export --include-raw-text`: 원문 전체까지 그래프에 포함합니다. 로컬 분석 목적일 때만 사용합니다.
- `graph stats`: 현재 RDF semantic store의 생성 시각, 항목 수, quad 수를 확인합니다.
- `graph quality`: Viewpoint Layer로 가기 전에 분류, 주제, insight seed, fallback 처리 여부 같은 준비 상태를 확인합니다.
- `interests`: 정리된 아카이브의 관심사 분포를 확인합니다.
- `concepts`: 태그/개념 분포를 확인합니다.
- `related`: 같은 관심사, 주제, 개념을 기준으로 관련 가능성이 있는 캡처를 읽기 전용으로 확인합니다.
- `insights`: 로컬에 저장된 draft insight note 목록을 확인합니다.
- `insights generate --period weekly --dry-run`: 이번 주의 처리 완료된 아카이브 항목으로 만들 수 있는 draft insight note를 미리 봅니다.
- `insights generate --period weekly`: Telegram으로 보내지 않고 로컬 SQLite에 draft insight note를 저장합니다.
- `insights show <insight-id>`: insight note와 근거 archive item을 함께 확인합니다.
- `process --no-codex`: Codex 없이 기본 추출만 실행합니다. 로컬 점검과 테스트용입니다.
- `list`: 최근 캡처와 정리 상태를 한 줄씩 확인합니다.
- `list --interest <interest>`: 특정 관심사로 정리된 항목만 확인합니다.
- `show`: 캡처 원본, 파일 경로, 정리된 제목/요약/포인트를 자세히 확인합니다.

## 정리되는 내용

다카이브봇은 단순히 "이미지를 저장했다"에서 끝나지 않고, 나중에 검색하고 다시 읽기 좋은 형태로 정리합니다.

- 제목: 나중에 목록에서 알아보기 쉬운 짧은 이름
- 핵심 요약: 캡처나 글이 말하는 실제 내용
- 주요 포인트: 중요한 주장, 사실, 관찰, 아이디어
- 관심사와 주제: AI, 커리어, 스포츠처럼 나중에 묶어 볼 기준
- 원문 텍스트: 이미지나 메시지에서 읽힌 텍스트
- 다시 볼 이유와 우선순위: 왜 나중에 다시 볼 만한지
- insight seed: 나중에 비슷한 항목들과 연결될 수 있는 작은 단서
- questions / relation candidates: 나중에 Viewpoint Layer에서 묶어 볼 질문과 연결 후보
- 태그와 언어 정보: 검색과 분류를 위한 보조 정보

기술적으로는 Codex가 캡처와 이미지를 읽어 구조화된 JSON을 만들고, Python 코드가 검증한 뒤 SQLite에 저장합니다. RDF semantic store와 JSON-LD export도 검증된 SQLite 행에서 Python 코드가 다시 생성합니다. Codex가 DB나 그래프 파일을 직접 수정하지는 않습니다.

정리 품질이 약한 항목은 `darchive reprocess-plan`으로 먼저 확인합니다. 이 단계는 관련 캡처, 반복 주제, insight note로 넘어가기 전에 아카이브의 관심사, 주제, 핵심 포인트, insight seed가 충분히 채워졌는지 확인하는 안전장치입니다. 실제 재처리는 `darchive reprocess --capture-id <capture-id>`처럼 하나의 캡처를 명시할 때만 실행합니다.

Draft insight note는 `darchive insights generate --period weekly`로 로컬에 생성할 수 있습니다. 평소에는 `darchive telegram-digest --kind weekly`가 먼저 짧은 Telegram 확인 카드로 "이번 주 insight draft를 만들지" 물어보는 흐름을 담당합니다. 실제 insight note 본문과 근거 archive item 확인은 SQLite와 로컬 명령에서 이뤄집니다.

## 주요 설정

```env
DARCHIVE_CODEX_ENABLED=true
DARCHIVE_CODEX_BIN=codex
DARCHIVE_CODEX_MODEL=
DARCHIVE_CODEX_SANDBOX=read-only
DARCHIVE_CODEX_EPHEMERAL=true
DARCHIVE_CODEX_TIMEOUT_SEC=900
```

`DARCHIVE_CODEX_BIN=codex`처럼 명령 이름만 넣어도 다카이브봇은 일반 PATH와 Homebrew 기본 경로(`/opt/homebrew/bin`, `/usr/local/bin`)에서 실행 파일을 찾습니다. launchd 환경이 터미널보다 PATH가 짧을 수 있으므로, 문제가 있으면 `/opt/homebrew/bin/codex`처럼 절대 경로로 적어도 됩니다.

## 앞으로 더해질 수 있는 것

다카이브봇은 먼저 캡처와 글을 안정적으로 모으고 관심사별로 정리하는 개인 아카이브로 시작합니다. 이후에는 Viewpoint Layer로 확장해 저장된 항목 사이의 관련성, 반복되는 관심사, 주간/월간 인사이트, Codex 논의 맥락, Telegram으로 다시 꺼내보기 같은 기능을 붙일 수 있습니다.

현재 남아 있는 사용성 갭은 명확합니다. Telegram 버튼 선택은 로컬에 감사 기록으로 남지만, 아직 선택 결과가 archive item의 분류 필드를 자동으로 재작성하거나 외부 시스템에 writeback하지는 않습니다. 검색은 SQLite FTS5 기반이며 vector search나 embedding retrieval은 일부러 넣지 않았습니다. 브라우저 확장, 자동 중복 병합, 선택 결과를 이용한 더 정교한 재처리 정책은 다음 단계 후보입니다.

Viewpoint Layer 방향은 [docs/viewpoint-layer.md](docs/viewpoint-layer.md)에 따로 정리합니다.
Insight synthesis 방향은 [docs/insight-synthesis.md](docs/insight-synthesis.md)에 따로 정리합니다.
Ontology-native graph 전환 방향은 [docs/ontology-graph.md](docs/ontology-graph.md)에 따로 정리합니다.

## macOS launchd

```bash
scripts/install_launch_agent.sh
scripts/uninstall_launch_agent.sh
```

설치 스크립트는 다섯 개의 LaunchAgent를 만듭니다.

- `com.hennei.darchivebot.telegram`: Telegram polling bot을 계속 실행합니다.
- `com.hennei.darchivebot.processor`: 5분마다 `darchive process --export-graph`를 실행합니다.
- `com.hennei.darchivebot.digest`: 매일 오전 9시에 `darchive telegram-digest --kind revisit`를 실행해 재방문 후보를 추천합니다.
- `com.hennei.darchivebot.digest.project-seed`: 매일 오후 6시에 `darchive telegram-digest --kind project-seed`를 실행해 프로젝트 씨앗 후보를 추천합니다.
- `com.hennei.darchivebot.digest.weekly`: 매일 오전 9시 30분에 `darchive telegram-digest --kind weekly`를 실행합니다. 주간 prompt key가 같으면 이미 보낸 prompt는 다시 보내지 않습니다.

일반 운영에서는 launchd가 poller를 계속 켜고 processor를 5분마다 실행하며, digest jobs가 오래된 아카이브에서 다시 볼 만한 후보, 프로젝트 씨앗 후보, 주간 insight 후보를 추천합니다. Processor는 먼저 SQLite에서 pending capture와 backoff 시간이 지난 retry 대상만 확인하고, 없으면 Codex를 호출하지 않고 종료합니다. 처리된 항목이 있을 때만 그래프 export를 실행합니다. 반복 실패한 항목은 `failed_blocked`로 멈춰 같은 실패가 5분마다 계속 쌓이지 않게 합니다. `darchive telegram`, `darchive pending`, `darchive process`, `darchive telegram-digest --dry-run` 직접 실행은 테스트/디버그용입니다.

## Troubleshooting

- `darchive list`에 아무 것도 없으면 `darchive telegram`이 실행 중인지 확인합니다.
- 그룹에서 일반 메시지나 사진이 안 잡히면 BotFather에서 Group Privacy를 끄거나 1:1 채팅으로 전환합니다.
- `HTTP Error 409: Conflict`가 로그에 있으면 같은 bot token으로 둘 이상의 polling bot이 실행 중인 상태입니다. token을 프로젝트별로 분리하거나 중복 poller를 종료합니다.
- 봇 추가/삭제 같은 Telegram 서비스 이벤트와 텍스트/캡션/파일이 없는 메시지는 capture로 저장하지 않습니다.
- `pending`이 비어 있으면 처리할 capture가 없다는 뜻입니다. 이 상태에서 scheduled processor가 실행되어도 Codex 작업은 발생하지 않습니다.

## 보안

`.env`, `.local/`, SQLite DB, 로그, 캡처 파일은 커밋하지 않습니다. Codex는 DB를 직접 수정하지 않고 구조화된 JSON만 반환합니다.

공개 전 점검:

```bash
scripts/preflight_public.sh
pytest
```
