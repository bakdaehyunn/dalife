from __future__ import annotations

from dalife.domains.course import CoursePlanningContext, compose_course_plan, persist_course_plan, plan_local_course
from dalife.domains.food import EvidenceTier, FoodEvidence, FoodPlace, FoodRecommendationContext, PlaceRanker
from dalife.domains.life import kst_datetime
from dalife.storage import ArchiveStore


def test_compose_course_plan_combines_life_food_and_archive_context(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="이태원", normalized_name="itaewon")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-1",
        name="Dinner Place",
        normalized_name="dinnerplace",
        area_id=area["id"],
    )
    routine = store.upsert_routine(routine_key="weekend-cleaning", title="주말 청소")
    reminder = store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="weekend-cleaning",
        title="주말 청소",
        cadence="weekly",
        action="청소하기",
    )
    event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="weekend-cleaning-2026-08-29",
        due_at="2026-08-29T14:00:00+09:00",
        status="pending",
    )
    capture_id = store.add_capture(
        capture_key="chat:course-planner",
        chat_id="chat",
        message_id=501,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="quiet dinner",
        caption="",
        content_kind="text",
        raw_message={"message_id": 501},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "Quiet Itaewon dinner",
            "core_summary": "Find a quiet dinner route",
            "raw_extracted_text": "이태원 조용한 저녁",
            "source_language": "ko",
            "primary_interest": "food",
            "topic": "course",
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    archive_item = store.get_archive_item(capture_id)
    assert archive_item is not None
    ranked_food = PlaceRanker().rank(
        [
            FoodPlace(
                name="Dinner Place",
                provider_place_id="place-1",
                provider="kakao",
                place_id=place["id"],
                category="저녁",
                evidence_tier=EvidenceTier.VERIFIED,
                evidence=(FoodEvidence(provider="naver_blog", url="https://blog.example/place-1", score=0.9),),
            )
        ],
        FoodRecommendationContext(area="이태원", topic="저녁"),
    )

    plan = compose_course_plan(
        context=CoursePlanningContext(
            title="이태원 저녁 코스",
            generated_at=kst_datetime("2026-08-29", "18:00"),
            area_id=area["id"],
            intent="home-area evening plan",
        ),
        food_candidates=ranked_food,
        due_life_events=[event],
        archive_items=[archive_item],
        max_stops=3,
    )

    assert [stop.source_domain for stop in plan.stops] == ["life", "food", "archive"]
    assert plan.stops[0].reminder_event_id == event["id"]
    assert plan.stops[1].place_id == place["id"]
    assert plan.stops[2].archive_item_id == archive_item["id"]


def test_persist_course_plan_stores_ordered_stops(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="이태원", normalized_name="itaewon")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-1",
        name="Dinner Place",
        normalized_name="dinnerplace",
        area_id=area["id"],
    )
    ranked_food = PlaceRanker().rank(
        [FoodPlace(name="Dinner Place", provider_place_id="place-1", provider="kakao", place_id=place["id"])],
        FoodRecommendationContext(area="이태원", topic="저녁"),
    )
    plan = compose_course_plan(
        context=CoursePlanningContext(
            title="이태원 저녁 코스",
            generated_at=kst_datetime("2026-08-29", "18:00"),
            area_id=area["id"],
        ),
        food_candidates=ranked_food,
        due_life_events=[],
        archive_items=[],
    )

    stored = persist_course_plan(store, plan)
    stops = store.list_course_plan_stops(course_plan_id=stored["id"])

    assert stored["title"] == "이태원 저녁 코스"
    assert stored["area_id"] == area["id"]
    assert [stop["stop_order"] for stop in stops] == [1]
    assert stops[0]["place_id"] == place["id"]
    assert stops[0]["source_domain"] == "food"


def test_plan_local_course_loads_food_life_and_archive_from_sqlite(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="이태원", normalized_name="이태원")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="dinner",
        name="이태원 저녁 식당",
        normalized_name="이태원저녁식당",
        area_id=area["id"],
        category="저녁",
    )
    routine = store.upsert_routine(routine_key="errand", title="장보기")
    reminder = store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="errand",
        title="장보기",
        cadence="one-off",
        action="장보기",
    )
    event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="errand:2026-08-29",
        due_at="2026-08-29T17:00:00+09:00",
        status="pending",
        response_payload={"title": "장보기"},
    )
    capture_id = store.add_capture(
        capture_key="course:context",
        chat_id="chat",
        message_id=1,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="이태원 저녁에 다시 가볼 곳",
        caption="",
        content_kind="text",
        raw_message={"message_id": 1},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "이태원 다시 갈 곳",
            "core_summary": "저녁 코스 후보",
            "raw_extracted_text": "이태원 저녁",
            "source_language": "ko",
            "primary_interest": "food",
            "topic": "이태원",
            "confidence": 0.9,
            "needs_review": False,
        },
    )

    result = plan_local_course(
        store,
        title="이태원 저녁 코스",
        area_name="이태원",
        generated_at=kst_datetime("2026-08-29", "18:00"),
        intent="이태원 저녁 코스",
        persist=True,
        max_stops=3,
    )

    assert result.area["id"] == area["id"]
    assert [stop.source_domain for stop in result.plan.stops] == ["life", "food", "archive"]
    assert result.plan.stops[0].title == "장보기"
    assert result.plan.stops[0].reminder_event_id == event["id"]
    assert result.plan.stops[1].place_id == place["id"]
    assert result.stored is not None


def test_course_does_not_turn_multiple_restaurants_into_sequential_stops():
    places = [
        FoodPlace(name=f"Restaurant {index}", provider_place_id=str(index), provider="kakao")
        for index in range(4)
    ]
    ranked = PlaceRanker().rank(places, FoodRecommendationContext(area="이태원", topic="저녁", count=4))

    plan = compose_course_plan(
        context=CoursePlanningContext(
            title="Dinner course",
            generated_at=kst_datetime("2026-08-29", "18:00"),
        ),
        food_candidates=ranked,
        due_life_events=[],
        archive_items=[],
        max_stops=4,
    )

    assert len(plan.stops) == 1
    assert plan.stops[0].source_domain == "food"
