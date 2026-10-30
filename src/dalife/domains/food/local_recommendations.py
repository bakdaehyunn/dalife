from __future__ import annotations

from dataclasses import dataclass

from dalife.domains.food.models import (
    EvidenceTier,
    FoodEvidence,
    FoodPlace,
    FoodRecommendationContext,
)
from dalife.domains.food.ranking import PlaceRanker, RankedFoodPlace
from dalife.domains.food.learning import build_preference_profile
from dalife.domains.food.recommendations import persist_food_recommendation_session
from dalife.models import AreaRecord, MobilityZoneRecord, UserFeedbackRecord
from dalife.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class LocalFoodRecommendation:
    area: AreaRecord | MobilityZoneRecord | None
    context: FoodRecommendationContext
    ranked_places: tuple[RankedFoodPlace, ...]
    session_id: str = ""


def normalize_area_name(value: str) -> str:
    return "".join(character.lower() for character in value if not character.isspace())


def recommend_local_food(
    store: PersonalContextRepositoryPort,
    *,
    request_text: str,
    context: FoodRecommendationContext,
    candidate_limit: int = 500,
    persist_session: bool = True,
) -> LocalFoodRecommendation:
    area = store.get_area_by_normalized_name(normalized_name=normalize_area_name(context.area))
    zone = store.get_mobility_zone(name=context.area) if area is None else None
    if area is None and zone is None:
        return LocalFoodRecommendation(area=None, context=context, ranked_places=())

    place_rows = (
        store.list_places(area_id=area["id"], limit=candidate_limit)
        if area is not None
        else store.list_zone_places(zone_id=zone["id"], limit=candidate_limit)
    )
    location = area or zone
    place_ids = [row["id"] for row in place_rows]
    links = store.list_place_evidence(place_ids=place_ids)
    evidence_ids = list(dict.fromkeys(link["evidence_item_id"] for link in links))
    evidence_by_id = {row["id"]: row for row in store.list_evidence_items(evidence_item_ids=evidence_ids)}

    links_by_place: dict[str, list] = {}
    for link in links:
        if link["evidence_item_id"] in evidence_by_id:
            links_by_place.setdefault(link["place_id"], []).append(link)

    feedback = store.list_user_feedback(domain="food", limit=10000)
    profile = build_preference_profile(store)
    recent_session_rows = store.list_recommendation_sessions(domain="food", limit=10)
    recently_shown = tuple(
        candidate["place_id"]
        for session in recent_session_rows
        for candidate in store.list_recommendation_candidates(session_id=session["id"])
        if candidate["place_id"]
    )
    hidden_place_ids = {
        row["place_id"] for row in feedback
        if row["place_id"] and row["action"] in {"hide", "hidden"}
    }
    ranked_context = FoodRecommendationContext(
        area=context.area,
        topic=context.topic,
        count=context.count,
        occasion=context.occasion,
        latitude=context.latitude if context.latitude is not None else location["center_latitude"],
        longitude=context.longitude if context.longitude is not None else location["center_longitude"],
        avoid_terms=context.avoid_terms,
        required_terms=context.required_terms,
        personal_signals={**feedback_signals(feedback), **context.personal_signals},
        category_preferences={
            normalize_area_name(key): value
            for key, value in profile.get("category_scores", {}).items()
        },
        recently_shown_place_ids=recently_shown,
        exploration_ratio=context.exploration_ratio,
    )
    places = [
        _food_place(row, links_by_place.get(row["id"], []), evidence_by_id)
        for row in place_rows
        if row["id"] not in hidden_place_ids
    ]
    ranked = tuple(PlaceRanker().rank(places, ranked_context))

    session_id = ""
    if persist_session:
        session = persist_food_recommendation_session(
            store,
            request_text=request_text,
            context=ranked_context,
            ranked_places=list(ranked),
            area_id=area["id"] if area is not None else "",
            status="completed" if ranked else "no_candidates",
        )
        session_id = session["id"]
    return LocalFoodRecommendation(
        area=location,
        context=ranked_context,
        ranked_places=ranked,
        session_id=session_id,
    )


def feedback_signals(rows: list[UserFeedbackRecord]) -> dict[str, float]:
    action_scores = {
        "liked": 0.95,
        "more_like_this": 0.9,
        "visited": 0.75,
        "disliked": 0.1,
        "hide": 0.0,
    }
    signals: dict[str, float] = {}
    for row in rows:
        place_id = row["place_id"]
        if place_id and place_id not in signals and row["action"] in action_scores:
            signals[place_id] = action_scores[row["action"]]
    return signals


def _food_place(place, links, evidence_by_id) -> FoodPlace:
    evidence = tuple(
        FoodEvidence(
            provider=evidence_by_id[link["evidence_item_id"]]["provider"],
            url=evidence_by_id[link["evidence_item_id"]]["url"],
            title=evidence_by_id[link["evidence_item_id"]]["title"],
            snippet=evidence_by_id[link["evidence_item_id"]]["snippet"],
            author=evidence_by_id[link["evidence_item_id"]]["author"],
            published_at=evidence_by_id[link["evidence_item_id"]]["published_at"],
            score=float(link["score"]),
        )
        for link in links
    )
    return FoodPlace(
        name=place["name"],
        provider_place_id=place["provider_place_id"],
        provider=place["provider"],
        place_id=place["id"],
        address=place["road_address"] or place["address"],
        map_url=place["map_url"],
        category=place["category"],
        latitude=place["latitude"],
        longitude=place["longitude"],
        evidence_tier=_evidence_tier(evidence),
        evidence=evidence,
    )


def _evidence_tier(evidence: tuple[FoodEvidence, ...]) -> EvidenceTier:
    strong_evidence = [item for item in evidence if item.score >= 0.7]
    unique_authors = {item.author for item in strong_evidence if item.author}
    if len(strong_evidence) >= 2 and len(unique_authors) >= 2:
        return EvidenceTier.VERIFIED
    if evidence:
        return EvidenceTier.PARTIAL
    return EvidenceTier.CANDIDATE
