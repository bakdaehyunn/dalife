from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from dalife.ports import PersonalContextRepositoryPort


PROFILE_VERSION = "food-profile-v1"
RANKER_VERSION = "food-ranker-v2"

POSITIVE_ACTIONS = {
    "map_requested": 0.15,
    "evidence_requested": 0.1,
    "saved": 0.45,
    "liked": 0.7,
    "more_like_this": 0.65,
    "visit_planned": 0.6,
    "visited": 0.8,
    "visit_confirmed": 1.0,
    "revisited": 1.0,
    "rating_submitted": 0.8,
}
NEGATIVE_ACTIONS = {"disliked": -0.8, "hide": -1.0, "hidden": -1.0, "visit_skipped": -0.25}


@dataclass(frozen=True)
class ZoneCoverage:
    zone_id: str
    zone_name: str
    place_count: int
    inside_count: int
    evidence_linked_count: int
    evidence_coverage: float


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def zone_coverage(store: PersonalContextRepositoryPort, zone: Any) -> ZoneCoverage:
    places = store.list_zone_places(zone_id=zone["id"], limit=10_000)
    inside = [
        place
        for place in places
        if place["latitude"] is not None
        and place["longitude"] is not None
        and haversine_meters(
            float(zone["center_latitude"]),
            float(zone["center_longitude"]),
            float(place["latitude"]),
            float(place["longitude"]),
        )
        <= int(zone["radius_meters"])
    ]
    links = store.list_place_evidence(place_ids=[place["id"] for place in inside]) if inside else []
    linked = len({link["place_id"] for link in links})
    return ZoneCoverage(
        zone_id=zone["id"],
        zone_name=zone["name"],
        place_count=len(places),
        inside_count=len(inside),
        evidence_linked_count=linked,
        evidence_coverage=round(linked / len(inside), 4) if inside else 0.0,
    )


def collection_report(store: PersonalContextRepositoryPort, *, days: int = 30) -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
    rows = store.list_query_ledger_run_metrics(since=since)
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("area_name") or "unassigned", row["provider"], row["facet"])
        group = groups.setdefault(
            key,
            {
                "area": key[0], "provider": key[1], "facet": key[2], "runs": 0,
                "yielded": 0, "new_places": 0, "refreshed_places": 0,
                "new_evidence": 0, "duplicate_evidence": 0, "new_links": 0,
                "high_quality_links": 0, "unmatched_evidence": 0, "failures": 0,
            },
        )
        group["runs"] += 1
        group["yielded"] += int(row["yielded_count"] or 0)
        for source, target in (
            ("new_places_count", "new_places"), ("refreshed_places_count", "refreshed_places"),
            ("new_evidence_count", "new_evidence"), ("duplicate_evidence_count", "duplicate_evidence"),
            ("new_links_count", "new_links"), ("high_quality_links_count", "high_quality_links"),
            ("unmatched_evidence_count", "unmatched_evidence"),
        ):
            group[target] += int(row.get(source) or 0)
        group["failures"] += int(row["status"] == "failed")
    results = []
    for group in groups.values():
        place_total = group["new_places"] + group["refreshed_places"]
        evidence_total = group["new_evidence"] + group["duplicate_evidence"]
        group["novelty_rate"] = round(group["new_places"] / place_total, 4) if place_total else 0.0
        group["duplicate_rate"] = round(group["duplicate_evidence"] / evidence_total, 4) if evidence_total else 0.0
        group["evidence_match_rate"] = round(group["new_links"] / group["new_evidence"], 4) if group["new_evidence"] else 0.0
        group["utility_score"] = round(
            group["new_places"] * 3 + group["high_quality_links"] * 2 + group["new_links"]
            - group["duplicate_evidence"] * 0.02 - group["failures"] * 5,
            3,
        )
        results.append(group)
    results.sort(key=lambda item: (-item["utility_score"], item["area"], item["provider"], item["facet"]))
    return {"days": days, "since": since, "runs": len(rows), "groups": results}


def build_preference_profile(store: PersonalContextRepositoryPort) -> dict[str, Any]:
    feedback = store.list_user_feedback(domain="food", limit=10_000)
    places = {place["id"]: place for place in store.list_places(limit=10_000)}
    category_scores: defaultdict[str, float] = defaultdict(float)
    place_scores: defaultdict[str, float] = defaultdict(float)
    action_counts: Counter[str] = Counter()
    strong_signals = 0
    for row in reversed(feedback):
        action = str(row["action"])
        weight = POSITIVE_ACTIONS.get(action, NEGATIVE_ACTIONS.get(action, 0.0))
        if not weight or not row["place_id"]:
            continue
        action_counts[action] += 1
        place_id = str(row["place_id"])
        place_scores[place_id] += weight
        place = places.get(place_id)
        if place:
            category = category_leaf(str(place["category"] or ""))
            if category:
                category_scores[category] += weight
        if abs(weight) >= 0.6:
            strong_signals += 1
    features = {
        "model_version": PROFILE_VERSION,
        "event_count": sum(action_counts.values()),
        "strong_signal_count": strong_signals,
        "confidence": round(min(1.0, strong_signals / 30), 4),
        "action_counts": dict(action_counts),
        "category_scores": normalized_scores(category_scores),
        "place_scores": normalized_scores(place_scores),
    }
    return features


def persist_preference_profile(store: PersonalContextRepositoryPort) -> Any:
    features = build_preference_profile(store)
    return store.create_preference_snapshot(
        domain="food",
        model_version=PROFILE_VERSION,
        features=features,
        evidence_count=int(features["event_count"]),
    )


def evaluate_recommendations(store: PersonalContextRepositoryPort, *, limit: int = 1000) -> dict[str, Any]:
    sessions = store.list_recommendation_sessions(domain="food", limit=limit)
    feedback = store.list_user_feedback(domain="food", limit=10_000)
    by_session: defaultdict[str, list[Any]] = defaultdict(list)
    for event in feedback:
        if event["recommendation_session_id"]:
            by_session[str(event["recommendation_session_id"])].append(event)
    evaluated = 0
    selected = 0
    negative = 0
    reciprocal_ranks: list[float] = []
    category_diversities: list[float] = []
    for session in sessions:
        candidates = store.list_recommendation_candidates(session_id=session["id"])
        if not candidates:
            continue
        evaluated += 1
        events = by_session.get(str(session["id"]), [])
        positive_places = {
            str(event["place_id"]) for event in events
            if event["place_id"] and event["action"] in POSITIVE_ACTIONS and POSITIVE_ACTIONS[event["action"]] >= 0.45
        }
        negative += sum(event["action"] in NEGATIVE_ACTIONS for event in events)
        if positive_places:
            selected += 1
            ranks = [int(row["rank"]) for row in candidates if row["place_id"] in positive_places and row["rank"]]
            if ranks:
                reciprocal_ranks.append(1 / min(ranks))
        categories = [
            category_leaf(str(json.loads(row["score_breakdown_json"] or "{}").get("category", "")))
            for row in candidates
        ]
        categories = [value for value in categories if value]
        category_diversities.append(len(set(categories)) / len(categories) if categories else 0.0)
    metrics = {
        "model_version": RANKER_VERSION,
        "session_count": evaluated,
        "sessions_with_positive_action": selected,
        "selection_rate": round(selected / evaluated, 4) if evaluated else 0.0,
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4) if reciprocal_ranks else 0.0,
        "negative_event_count": negative,
        "category_diversity": round(sum(category_diversities) / len(category_diversities), 4) if category_diversities else 0.0,
    }
    store.create_recommendation_evaluation(
        domain="food", model_version=RANKER_VERSION, metrics=metrics, session_count=evaluated
    )
    return metrics


def category_leaf(value: str) -> str:
    return value.split(">")[-1].strip().lower() if value else ""


def normalized_scores(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    scale = max(1.0, max(abs(value) for value in values.values()))
    return {key: round(max(-1.0, min(1.0, value / scale)), 4) for key, value in sorted(values.items())}
