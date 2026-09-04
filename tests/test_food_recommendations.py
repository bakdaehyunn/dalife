from __future__ import annotations

from darchivebot.domains.food import (
    EvidenceTier,
    FoodEvidence,
    FoodPlace,
    FoodRecommendationContext,
    PlaceRanker,
    persist_food_recommendation_session,
)
from darchivebot.storage import ArchiveStore


def test_persist_food_recommendation_session_records_ranked_candidates(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="20551759",
        name="미성참숯정육식당",
        normalized_name="미성참숯정육식당",
        area_id=area["id"],
    )
    context = FoodRecommendationContext(area="신정동", topic="고기 저녁", count=3)
    ranked = PlaceRanker().rank(
        [
            FoodPlace(
                name="미성참숯정육식당",
                provider_place_id="20551759",
                provider="kakao",
                place_id=place["id"],
                category="고기",
                evidence_tier=EvidenceTier.VERIFIED,
                evidence=(FoodEvidence(provider="naver_blog", url="https://blog.example/1", title="고기 후기", score=0.9),),
            )
        ],
        context,
    )

    session = persist_food_recommendation_session(
        store,
        request_text="신정동 고기 추천",
        context=context,
        ranked_places=ranked,
        area_id=area["id"],
    )
    candidates = store.list_recommendation_candidates(session_id=session["id"])

    assert session["domain"] == "food"
    assert session["area_id"] == area["id"]
    assert session["request_text"] == "신정동 고기 추천"
    assert len(candidates) == 1
    assert candidates[0]["place_id"] == place["id"]
    assert candidates[0]["rank"] == 1
    assert candidates[0]["evidence_tier"] == "verified"
    assert candidates[0]["score"] == ranked[0].score
