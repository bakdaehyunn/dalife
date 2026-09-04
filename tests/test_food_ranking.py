from __future__ import annotations

from darchivebot.domains.food import (
    EvidenceTier,
    FoodEvidence,
    FoodPlace,
    FoodRecommendationContext,
    PlaceRanker,
)
from darchivebot.domains.food.ranking import distance_score, evidence_score


def test_place_ranker_prioritizes_evidence_and_personal_fit():
    context = FoodRecommendationContext(
        area="신정동",
        topic="고기 저녁",
        personal_signals={"고기": 0.95},
    )
    strong = FoodPlace(
        name="미성참숯정육식당",
        provider_place_id="1",
        provider="kakao",
        category="고기",
        evidence_tier=EvidenceTier.VERIFIED,
        evidence=(
            FoodEvidence(provider="naver_blog", url="https://blog.example/1", title="고기 후기", score=0.9, author="a"),
            FoodEvidence(provider="naver_blog", url="https://blog.example/2", title="저녁 후기", score=0.8, author="b"),
        ),
    )
    weak = FoodPlace(
        name="가벼운 샐러드",
        provider_place_id="2",
        provider="kakao",
        category="샐러드",
        evidence_tier=EvidenceTier.CANDIDATE,
        evidence=(FoodEvidence(provider="naver_blog", url="https://blog.example/3", title="점심", score=0.3),),
    )

    ranked = PlaceRanker().rank([weak, strong], context)

    assert ranked[0].place == strong
    assert ranked[0].breakdown["evidence"] > ranked[1].breakdown["evidence"]
    assert ranked[0].breakdown["personal"] > ranked[1].breakdown["personal"]


def test_place_ranker_applies_avoid_term_penalty():
    context = FoodRecommendationContext(area="이태원", topic="저녁", avoid_terms=("웨이팅",))
    crowded = FoodPlace(
        name="인기식당",
        provider_place_id="1",
        provider="kakao",
        category="양식",
        evidence_tier=EvidenceTier.VERIFIED,
        evidence=(FoodEvidence(provider="naver_blog", url="https://blog.example/1", snippet="웨이팅이 길다", score=0.9),),
    )
    quiet = FoodPlace(
        name="조용한식당",
        provider_place_id="2",
        provider="kakao",
        category="양식",
        evidence_tier=EvidenceTier.PARTIAL,
        evidence=(FoodEvidence(provider="naver_blog", url="https://blog.example/2", snippet="조용한 저녁", score=0.7),),
    )

    ranked = PlaceRanker().rank([crowded, quiet], context)

    assert ranked[0].place == quiet
    assert ranked[1].breakdown["risk"] == 1.0


def test_distance_score_prefers_nearby_places_when_location_is_known():
    context = FoodRecommendationContext(area="이태원", topic="점심", latitude=37.534, longitude=126.994)
    near = FoodPlace(
        name="Near",
        provider_place_id="1",
        provider="kakao",
        latitude=37.5341,
        longitude=126.9941,
    )
    far = FoodPlace(
        name="Far",
        provider_place_id="2",
        provider="kakao",
        latitude=37.57,
        longitude=127.02,
    )

    assert distance_score(near, context) > distance_score(far, context)


def test_evidence_score_rewards_unique_authors():
    one_author = FoodPlace(
        name="A",
        provider_place_id="1",
        provider="kakao",
        evidence_tier=EvidenceTier.VERIFIED,
        evidence=(
            FoodEvidence(provider="naver_blog", url="https://blog.example/1", author="same", score=0.8),
            FoodEvidence(provider="naver_blog", url="https://blog.example/2", author="same", score=0.8),
        ),
    )
    two_authors = FoodPlace(
        name="B",
        provider_place_id="2",
        provider="kakao",
        evidence_tier=EvidenceTier.VERIFIED,
        evidence=(
            FoodEvidence(provider="naver_blog", url="https://blog.example/3", author="one", score=0.8),
            FoodEvidence(provider="naver_blog", url="https://blog.example/4", author="two", score=0.8),
        ),
    )

    assert evidence_score(two_authors) > evidence_score(one_author)


def test_place_ranker_keeps_result_count_limit_after_diversity_adjustment():
    places = [
        FoodPlace(name=f"Place {index}", provider_place_id=str(index), provider="kakao", category="고기")
        for index in range(5)
    ]
    context = FoodRecommendationContext(area="신정동", topic="고기", count=3)

    ranked = PlaceRanker().rank(places, context)

    assert len(ranked) == 3
