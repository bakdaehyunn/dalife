from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dalife.models import UserFeedbackRecord
from dalife.ports import PersonalContextRepositoryPort


class FoodFeedbackAction(StrEnum):
    RECOMMENDATION_SHOWN = "recommendation_shown"
    MAP_REQUESTED = "map_requested"
    EVIDENCE_REQUESTED = "evidence_requested"
    SAVED = "saved"
    LIKED = "liked"
    DISLIKED = "disliked"
    VISITED = "visited"
    HIDE = "hide"
    MORE_LIKE_THIS = "more_like_this"
    VISIT_PLANNED = "visit_planned"
    VISIT_CONFIRMED = "visit_confirmed"
    VISIT_SKIPPED = "visit_skipped"
    REVISITED = "revisited"


FOOD_FEEDBACK_CHOICES = (
    {"choice": FoodFeedbackAction.LIKED.value, "label": "Liked"},
    {"choice": FoodFeedbackAction.DISLIKED.value, "label": "Disliked"},
    {"choice": FoodFeedbackAction.VISITED.value, "label": "Visited"},
    {"choice": FoodFeedbackAction.HIDE.value, "label": "Hide"},
    {"choice": FoodFeedbackAction.MORE_LIKE_THIS.value, "label": "More like this"},
    {"choice": FoodFeedbackAction.MAP_REQUESTED.value, "label": "Map"},
    {"choice": FoodFeedbackAction.EVIDENCE_REQUESTED.value, "label": "Evidence"},
    {"choice": FoodFeedbackAction.SAVED.value, "label": "Save"},
    {"choice": FoodFeedbackAction.VISIT_PLANNED.value, "label": "Plan visit"},
)


@dataclass(frozen=True)
class FoodFeedback:
    feedback_key: str
    action: FoodFeedbackAction
    place_id: str
    recommendation_session_id: str = ""
    course_plan_id: str = ""


def record_food_feedback(
    store: PersonalContextRepositoryPort,
    feedback: FoodFeedback,
) -> UserFeedbackRecord:
    return store.record_user_feedback(
        feedback_key=feedback.feedback_key,
        domain="food",
        action=feedback.action.value,
        place_id=feedback.place_id,
        recommendation_session_id=feedback.recommendation_session_id,
        course_plan_id=feedback.course_plan_id,
        payload={"source": "food_feedback"},
    )
