from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class FoodParsedRequest:
    intent: str
    area: str = ""
    topic: str = ""
    meal_type: str = ""
    budget: str = ""
    occasion: str = ""
    count: int = 30


class EvidenceTier(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    CANDIDATE = "candidate"
    NEEDS_REFRESH = "needs_refresh"


@dataclass(frozen=True)
class FoodEvidence:
    provider: str
    url: str
    title: str = ""
    snippet: str = ""
    author: str = ""
    published_at: str = ""
    score: float = 0.0


@dataclass(frozen=True)
class FoodPlace:
    name: str
    provider_place_id: str
    provider: str
    place_id: str = ""
    address: str = ""
    map_url: str = ""
    category: str = ""
    latitude: float | None = None
    longitude: float | None = None
    evidence_tier: EvidenceTier = EvidenceTier.CANDIDATE
    evidence: tuple[FoodEvidence, ...] = ()


@dataclass(frozen=True)
class FoodRecommendationContext:
    area: str
    topic: str
    count: int = 30
    occasion: str = ""
    latitude: float | None = None
    longitude: float | None = None
    avoid_terms: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    personal_signals: dict[str, float] = field(default_factory=dict)
