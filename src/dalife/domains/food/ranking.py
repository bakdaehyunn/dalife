from __future__ import annotations

import math
from dataclasses import dataclass

from dalife.domains.food.models import EvidenceTier, FoodPlace, FoodRecommendationContext


@dataclass(frozen=True)
class RankedFoodPlace:
    place: FoodPlace
    score: float
    breakdown: dict[str, float]


class PlaceRanker:
    def rank(self, places: list[FoodPlace], context: FoodRecommendationContext) -> list[RankedFoodPlace]:
        ranked = [self.score(place, context) for place in places]
        ranked.sort(key=lambda item: (-item.score, item.place.name))
        return self._apply_category_diversity(ranked)[: context.count]

    def score(self, place: FoodPlace, context: FoodRecommendationContext) -> RankedFoodPlace:
        breakdown = {
            "evidence": evidence_score(place),
            "name_match": name_match_score(place, context),
            "menu_fit": menu_fit_score(place, context),
            "distance": distance_score(place, context),
            "personal": personal_signal_score(place, context),
            "risk": risk_penalty(place, context),
        }
        score = (
            breakdown["evidence"] * 0.35
            + breakdown["name_match"] * 0.15
            + breakdown["menu_fit"] * 0.20
            + breakdown["distance"] * 0.10
            + breakdown["personal"] * 0.20
            - breakdown["risk"] * 0.30
        )
        return RankedFoodPlace(place=place, score=round(score, 4), breakdown=breakdown)

    def _apply_category_diversity(self, ranked: list[RankedFoodPlace]) -> list[RankedFoodPlace]:
        category_counts: dict[str, int] = {}
        diversified: list[RankedFoodPlace] = []
        for item in ranked:
            category = item.place.category.strip().lower()
            count = category_counts.get(category, 0)
            if category and count:
                adjusted = RankedFoodPlace(
                    place=item.place,
                    score=round(item.score - min(count * 0.04, 0.16), 4),
                    breakdown={**item.breakdown, "diversity_penalty": round(min(count * 0.04, 0.16), 4)},
                )
            else:
                adjusted = item
            category_counts[category] = count + 1
            diversified.append(adjusted)
        diversified.sort(key=lambda item: (-item.score, item.place.name))
        return diversified


def evidence_score(place: FoodPlace) -> float:
    tier_base = {
        EvidenceTier.VERIFIED: 0.9,
        EvidenceTier.PARTIAL: 0.65,
        EvidenceTier.CANDIDATE: 0.35,
        EvidenceTier.NEEDS_REFRESH: 0.25,
    }[place.evidence_tier]
    if not place.evidence:
        return tier_base
    average = sum(max(0.0, min(1.0, item.score)) for item in place.evidence) / len(place.evidence)
    unique_authors = {item.author for item in place.evidence if item.author}
    author_bonus = min(len(unique_authors) * 0.03, 0.12)
    return min(1.0, tier_base * 0.65 + average * 0.35 + author_bonus)


def name_match_score(place: FoodPlace, context: FoodRecommendationContext) -> float:
    terms = normalized_terms((context.topic, context.occasion, *context.required_terms))
    haystack = normalize(" ".join([place.name, place.category, *evidence_texts(place)]))
    if not terms:
        return 0.0
    return sum(1 for term in terms if term in haystack) / len(terms)


def menu_fit_score(place: FoodPlace, context: FoodRecommendationContext) -> float:
    terms = normalized_terms((context.topic, context.occasion, *context.required_terms))
    haystack = normalize(" ".join([place.category, *evidence_texts(place)]))
    if not terms:
        return 0.5
    return min(1.0, sum(1 for term in terms if term in haystack) / max(1, min(len(terms), 3)))


def distance_score(place: FoodPlace, context: FoodRecommendationContext) -> float:
    if None in (place.latitude, place.longitude, context.latitude, context.longitude):
        return 0.5
    km = haversine_km(context.latitude, context.longitude, place.latitude, place.longitude)
    if km <= 0.5:
        return 1.0
    if km >= 5.0:
        return 0.0
    return round(1.0 - ((km - 0.5) / 4.5), 4)


def personal_signal_score(place: FoodPlace, context: FoodRecommendationContext) -> float:
    if not context.personal_signals:
        return 0.5
    keys = normalized_terms((place.place_id, place.provider_place_id, place.name, place.category))
    scores = [context.personal_signals[key] for key in keys if key in context.personal_signals]
    if not scores:
        return 0.5
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def risk_penalty(place: FoodPlace, context: FoodRecommendationContext) -> float:
    avoid_terms = normalized_terms(context.avoid_terms)
    haystack = normalize(" ".join([place.name, place.category, *evidence_texts(place)]))
    if not avoid_terms:
        return 0.0
    return min(1.0, sum(1 for term in avoid_terms if term in haystack) / len(avoid_terms))


def evidence_texts(place: FoodPlace) -> list[str]:
    return [f"{item.title} {item.snippet}" for item in place.evidence]


def normalized_terms(values: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for value in values:
        for term in value.lower().split():
            compacted = normalize(term)
            if compacted:
                terms.append(compacted)
    return tuple(terms)


def normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if not ch.isspace())


def haversine_km(
    latitude_a: float | None,
    longitude_a: float | None,
    latitude_b: float | None,
    longitude_b: float | None,
) -> float:
    if None in (latitude_a, longitude_a, latitude_b, longitude_b):
        return math.inf
    radius_km = 6371.0
    lat1 = math.radians(latitude_a)
    lat2 = math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
