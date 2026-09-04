from __future__ import annotations

from darchivebot.domains.food import (
    EvidenceTier,
    FoodRecommendationContext,
    recommend_local_food,
)
from darchivebot.storage import ArchiveStore


def _seed_place(store, area_id: str, *, place_id: str, name: str, category: str):
    return store.upsert_place(
        provider="kakao_local",
        provider_place_id=place_id,
        name=name,
        normalized_name=name.replace(" ", "").lower(),
        area_id=area_id,
        category=category,
        road_address=f"서울 {name}길 1",
        map_url=f"https://place.map.kakao.com/{place_id}",
    )


def _link_evidence(store, place_id: str, suffix: str, *, author: str, score: float, title: str):
    evidence = store.upsert_evidence_item(
        provider="naver_blog",
        url=f"https://blog.example/{suffix}",
        title=title,
        snippet=f"{title} 상세 후기",
        author=author,
    )
    store.link_place_evidence(
        place_id=place_id,
        evidence_item_id=evidence["id"],
        match_type="exact_name",
        score=score,
        decision="matched",
    )


def test_recommend_local_food_loads_and_ranks_validated_sqlite_rows(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(
        name="신정동",
        normalized_name="신정동",
        center_latitude=37.52,
        center_longitude=126.86,
    )
    meat = _seed_place(store, area["id"], place_id="meat", name="참숯 고깃집", category="고기")
    salad = _seed_place(store, area["id"], place_id="salad", name="가벼운 샐러드", category="샐러드")
    _link_evidence(store, meat["id"], "meat-1", author="author-a", score=0.9, title="신정동 고기 저녁")
    _link_evidence(store, meat["id"], "meat-2", author="author-b", score=0.85, title="참숯 고깃집 후기")
    _link_evidence(store, salad["id"], "salad-1", author="author-c", score=0.5, title="샐러드 점심")

    result = recommend_local_food(
        store,
        request_text="신정동 고기 저녁 추천",
        context=FoodRecommendationContext(area="신 정 동", topic="고기 저녁", count=2),
    )

    assert result.area is not None
    assert [item.place.name for item in result.ranked_places] == ["참숯 고깃집", "가벼운 샐러드"]
    assert result.ranked_places[0].place.evidence_tier == EvidenceTier.VERIFIED
    assert result.ranked_places[1].place.evidence_tier == EvidenceTier.PARTIAL
    assert result.context.latitude == 37.52
    assert result.session_id
    candidates = store.list_recommendation_candidates(session_id=result.session_id)
    assert [row["place_id"] for row in candidates] == [meat["id"], salad["id"]]


def test_recommend_local_food_uses_feedback_and_ignores_rejected_evidence(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="이태원", normalized_name="이태원")
    liked = _seed_place(store, area["id"], place_id="liked", name="취향 식당", category="한식")
    other = _seed_place(store, area["id"], place_id="other", name="보통 식당", category="한식")
    rejected = store.upsert_evidence_item(
        provider="naver_blog",
        url="https://blog.example/rejected",
        title="unrelated",
        snippet="not this place",
    )
    store.link_place_evidence(
        place_id=other["id"],
        evidence_item_id=rejected["id"],
        match_type="weak",
        score=0.99,
        decision="rejected",
    )
    store.record_user_feedback(
        feedback_key="food:liked:liked",
        domain="food",
        action="liked",
        place_id=liked["id"],
    )

    result = recommend_local_food(
        store,
        request_text="이태원 한식 추천",
        context=FoodRecommendationContext(area="이태원", topic="한식", count=2),
    )

    assert result.ranked_places[0].place.place_id == liked["id"]
    other_result = next(item for item in result.ranked_places if item.place.place_id == other["id"])
    assert other_result.place.evidence == ()
    assert other_result.place.evidence_tier == EvidenceTier.CANDIDATE


def test_recommend_local_food_does_not_create_area_or_session_when_area_is_unknown(tmp_path):
    store = ArchiveStore(tmp_path / "state")

    result = recommend_local_food(
        store,
        request_text="없는동네 추천",
        context=FoodRecommendationContext(area="없는동네", topic="저녁"),
    )

    assert result.area is None
    assert result.ranked_places == ()
    assert result.session_id == ""
    assert store.get_area_by_normalized_name(normalized_name="없는동네") is None
