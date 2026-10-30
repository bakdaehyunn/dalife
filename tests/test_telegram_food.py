from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dalife.storage import ArchiveStore
from dalife.telegram_food import (
    apply_food_feedback_callback,
    parse_food_feedback_callback,
    recommend_food_for_telegram,
    send_due_food_visit_followups,
)


class _FakeTelegramApi:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, *, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))
        return {"result": {"message_id": 42}}


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


def test_map_callback_records_request_and_returns_target_url(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = _seed_food(store)
    result = recommend_food_for_telegram(store, "신정동 맛집 1곳 추천")

    answer = apply_food_feedback_callback(
        store,
        f"food:{result.session_id}:1:map_requested",
        callback_query_id="callback-map",
    )

    assert answer == "MAP:https://place.map.kakao.com/place-1"
    feedback = store.list_user_feedback(domain="food", limit=10)
    assert feedback[0]["place_id"] == place["id"]
    assert feedback[0]["action"] == "map_requested"


def test_evidence_callback_records_request_and_returns_sources(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = _seed_food(store)
    evidence = store.upsert_evidence_item(
        provider="naver_blog",
        url="https://blog.naver.com/example/post-1",
        title="동네 식당 방문 후기",
        snippet="직접 방문한 후기",
    )
    store.link_place_evidence(
        place_id=place["id"],
        evidence_item_id=evidence["id"],
        match_type="exact_name",
        score=0.9,
        decision="matched",
    )
    result = recommend_food_for_telegram(store, "신정동 맛집 1곳 추천")

    answer = apply_food_feedback_callback(
        store,
        f"food:{result.session_id}:1:evidence_requested",
        callback_query_id="callback-evidence",
    )

    assert answer and answer.startswith("EVIDENCE:")
    assert "동네 식당 방문 후기" in answer
    assert "https://blog.naver.com/example/post-1" in answer
    assert store.list_user_feedback(domain="food", limit=10)[0]["action"] == "evidence_requested"


def test_every_recommendation_has_a_compact_unambiguous_keyboard(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    for index in range(9):
        store.upsert_place(
            provider="kakao_local",
            provider_place_id=f"place-{index}",
            name=f"동네 식당 {index}",
            normalized_name=f"동네식당{index}",
            area_id=area["id"],
            category="한식",
            map_url=f"https://place.map.kakao.com/place-{index}",
        )

    result = recommend_food_for_telegram(store, "신정동 맛집 9곳 추천")

    assert len(result.messages) == 9
    assert all(message.reply_markup for message in result.messages)
    assert all("place.map.kakao.com" not in message.text for message in result.messages)
    for rank, message in enumerate(result.messages, start=1):
        assert message.text.startswith(f"{rank}/9")
        keyboard = message.reply_markup["inline_keyboard"]
        assert len(keyboard) == 2
        assert [button["text"] for row in keyboard for button in row] == [
            "지도", "근거", "저장", "좋아요", "별로", "방문 예정",
        ]
        assert all(
            f":{rank}:" in button["callback_data"]
            for row in keyboard
            for button in row
        )


def test_visit_plan_sends_due_prompt_and_confirmation_closes_followup(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = _seed_food(store)
    result = recommend_food_for_telegram(store, "신정동 맛집 1곳 추천")
    callback = f"food:{result.session_id}:1:visit_planned"

    answer = apply_food_feedback_callback(
        store,
        callback,
        callback_query_id="callback-plan",
        chat_id="1234",
    )
    assert answer == "Saved: Plan visit"

    api = _FakeTelegramApi()
    delivery = send_due_food_visit_followups(
        store,
        api,
        default_chat_id="fallback",
        now=datetime.now(timezone.utc) + timedelta(hours=25),
    )

    assert delivery == {"due": 1, "sent": 1}
    assert api.messages[0][0] == "1234"
    assert "동네 식당" in api.messages[0][1]
    confirm_callback = api.messages[0][2]["inline_keyboard"][0][0]["callback_data"]
    assert confirm_callback.endswith(":visit_confirmed")

    confirmed = apply_food_feedback_callback(
        store,
        confirm_callback,
        callback_query_id="callback-confirm",
        chat_id="1234",
    )
    assert confirmed == "Saved: Visited"
    followups = store.list_due_food_visit_followups(
        due_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        limit=10,
    )
    assert followups == []
    feedback = store.list_user_feedback(domain="food", limit=10)
    assert feedback[0]["place_id"] == place["id"]
    assert feedback[0]["action"] == "visit_confirmed"


def test_food_telegram_requests_area_when_location_is_missing(tmp_path):
    store = ArchiveStore(tmp_path / "state")

    result = recommend_food_for_telegram(store, "현재 위치 맛집 추천")

    assert result.session_id == ""
    assert "동네나 역 이름" in result.messages[0].text
