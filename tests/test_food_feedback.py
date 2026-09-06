from __future__ import annotations

from dalife.domains.food import FOOD_FEEDBACK_CHOICES, FoodFeedback, FoodFeedbackAction, record_food_feedback
from dalife.storage import ArchiveStore


def test_food_feedback_actions_match_target_telegram_actions():
    assert tuple(choice["choice"] for choice in FOOD_FEEDBACK_CHOICES) == (
        "liked",
        "disliked",
        "visited",
        "hide",
        "more_like_this",
    )


def test_record_food_feedback_persists_personal_signal(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-1",
        name="Dinner Place",
        normalized_name="dinnerplace",
    )

    first = record_food_feedback(
        store,
        FoodFeedback(
            feedback_key="telegram:cb-1",
            action=FoodFeedbackAction.LIKED,
            place_id=place["id"],
        ),
    )
    second = record_food_feedback(
        store,
        FoodFeedback(
            feedback_key="telegram:cb-1",
            action=FoodFeedbackAction.MORE_LIKE_THIS,
            place_id=place["id"],
        ),
    )
    rows = store.list_user_feedback(domain="food", limit=10)

    assert first["id"] == second["id"]
    assert second["domain"] == "food"
    assert second["action"] == "more_like_this"
    assert second["place_id"] == place["id"]
    assert [row["id"] for row in rows] == [first["id"]]
