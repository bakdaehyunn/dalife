from __future__ import annotations

from dalife.storage import ArchiveStore
from dalife.telegram_food import (
    apply_food_feedback_callback,
    parse_food_feedback_callback,
    recommend_food_for_telegram,
)


def _seed_food(store: ArchiveStore):
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao_local",
        provider_place_id="place-1",
        name="동네 식당",
        normalized_name="동네식당",
        area_id=area["id"],
        category="한식",
        road_address="서울 양천구 신정동 1",
        map_url="https://place.map.kakao.com/place-1",
    )
    return place


def test_food_telegram_response_persists_session_and_uses_bounded_callbacks(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = _seed_food(store)

    result = recommend_food_for_telegram(store, "신정동 한식 맛집 1곳 추천")

    assert result.returned_count == 1
    assert result.session_id
    assert "동네 식당" in result.messages[0].text
    callbacks = [
        button["callback_data"]
        for row in result.messages[0].reply_markup["inline_keyboard"]
        for button in row
    ]
    assert all(len(value.encode("utf-8")) <= 64 for value in callbacks)
    assert parse_food_feedback_callback(callbacks[0]) is not None
    candidates = store.list_recommendation_candidates(session_id=result.session_id)
    assert candidates[0]["place_id"] == place["id"]


def test_food_feedback_callback_resolves_persisted_candidate(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = _seed_food(store)
    result = recommend_food_for_telegram(store, "신정동 맛집 1곳 추천")

    answer = apply_food_feedback_callback(
        store,
        f"food:{result.session_id}:1:more_like_this",
        callback_query_id="callback-1",
    )

    assert answer == "Saved: More like this"
    feedback = store.list_user_feedback(domain="food", limit=10)
    assert feedback[0]["place_id"] == place["id"]
    assert feedback[0]["action"] == "more_like_this"


def test_food_telegram_requests_area_when_location_is_missing(tmp_path):
    store = ArchiveStore(tmp_path / "state")

    result = recommend_food_for_telegram(store, "현재 위치 맛집 추천")

    assert result.session_id == ""
    assert "동네나 역 이름" in result.messages[0].text
