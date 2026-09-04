from __future__ import annotations

from darchivebot.domains.food.models import FoodRecommendationContext
from darchivebot.domains.food.ranking import RankedFoodPlace
from darchivebot.models import RecommendationSessionRecord
from darchivebot.ports import PersonalContextRepositoryPort


def persist_food_recommendation_session(
    store: PersonalContextRepositoryPort,
    *,
    request_text: str,
    context: FoodRecommendationContext,
    ranked_places: list[RankedFoodPlace],
    area_id: str = "",
    status: str = "completed",
) -> RecommendationSessionRecord:
    session = store.create_recommendation_session(
        domain="food",
        request_text=request_text,
        area_id=area_id,
        status=status,
        context={
            "area": context.area,
            "topic": context.topic,
            "count": context.count,
            "occasion": context.occasion,
            "avoid_terms": list(context.avoid_terms),
            "required_terms": list(context.required_terms),
        },
    )
    for index, ranked in enumerate(ranked_places, start=1):
        store.add_recommendation_candidate(
            session_id=session["id"],
            place_id=ranked.place.place_id,
            rank=index,
            score=ranked.score,
            score_breakdown=ranked.breakdown,
            evidence_tier=ranked.place.evidence_tier.value,
            explanation=f"{ranked.place.name} matched {context.topic}".strip(),
        )
    return session
