from __future__ import annotations

from dalife.domains.food import parse_food_request


def test_parse_food_area_and_topic():
    parsed = parse_food_request("서면에서 해장할 건데 국밥 감자탕 위주로 추천해줘")

    assert parsed.intent == "start"
    assert parsed.area == "서면"
    assert "국밥" in parsed.topic
    assert "감자탕" in parsed.topic


def test_parse_food_rejects_non_food_work_requests():
    assert parse_food_request("오늘 회의록 정리해줘").intent == "unknown"

    examples = [
        "서울 맛집 데이터 정리해줘",
        "강남역 맛집 보고서 작성해줘",
        "부산 서면 국밥 시장 분석해줘",
        "대구 동성로 맛집 리스트 엑셀로 만들어줘",
        "홍대입구 식당 매출 자료 찾아줘",
        "제주공항 근처 밥집 회의자료 준비해줘",
    ]
    for text in examples:
        assert parse_food_request(text).intent == "unknown", text


def test_parse_food_current_location_request_needs_location():
    parsed = parse_food_request("내 주변 야식 맛집 추천")

    assert parsed.intent == "needs_location"
    assert parsed.area == ""
    assert "야식" in parsed.topic
    assert parsed.meal_type == "야식"


def test_parse_food_keeps_named_nearby_area():
    parsed = parse_food_request("목동역 근처 맛집 추천")

    assert parsed.intent == "start"
    assert parsed.area == "목동역"
    assert parsed.topic == "맛집"


def test_parse_food_cafe_fast_food_and_exact_food_topics():
    coffee = parse_food_request("목동역 커피 추천")
    dessert = parse_food_request("연남동 디저트 카페 추천")
    refill = parse_food_request("목동역 무한리필 샤브샤브 맛집 추천")

    assert coffee.area == "목동역"
    assert coffee.topic == "커피"
    assert dessert.area == "연남동"
    assert "디저트" in dessert.topic
    assert "카페" in dessert.topic
    assert refill.area == "목동역"
    assert "무한리필" in refill.topic
    assert "샤브샤브" in refill.topic


def test_parse_food_common_korean_area_shapes():
    examples = {
        "강남역 맛집 추천": "강남역",
        "홍대입구 혼밥 추천": "홍대입구",
        "성수동 데이트 맛집": "성수동",
        "부산 서면 국밥 추천": "부산 서면",
        "대구 동성로 맛집 추천": "대구 동성로",
        "수원역 점심 추천": "수원역",
        "전주 한옥마을 맛집 추천": "전주 한옥마을",
        "해운대 해수욕장 근처 맛집": "해운대 해수욕장",
        "제주공항 근처 밥집 추천": "제주공항",
        "인천 송도 센트럴파크 맛집 추천": "인천 송도 센트럴파크",
    }

    for text, expected_area in examples.items():
        parsed = parse_food_request(text)
        assert parsed.intent == "start", text
        assert parsed.area == expected_area, text


def test_parse_food_command_prefix_overrides_work_words():
    parsed = parse_food_request("/맛집 서울 맛집 데이터 정리해줘")

    assert parsed.intent == "start"
    assert parsed.area == "서울"
