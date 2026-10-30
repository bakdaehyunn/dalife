from __future__ import annotations

from dalife.domains.food.learning import (
    build_preference_profile,
    collection_report,
    evaluate_recommendations,
    haversine_meters,
    persist_preference_profile,
    zone_coverage,
)
from dalife.storage import ArchiveStore


def seed_place(store, area_id, key, category="음식점 > 한식"):
    return store.upsert_place(
        provider="kakao_local",
        provider_place_id=key,
        name=key,
        normalized_name=key,
        area_id=area_id,
        category=category,
        latitude=37.5201,
        longitude=126.8601,
    )


def test_mobility_zone_coverage_uses_radius_and_evidence(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = seed_place(store, area["id"], "near")
    zone = store.upsert_mobility_zone(
        name="home-walk", kind="home", center_latitude=37.52,
        center_longitude=126.86, radius_meters=1000, walk_minutes=15,
    )
    store.link_mobility_zone_area(zone_id=zone["id"], area_id=area["id"])
    evidence = store.upsert_evidence_item(
        provider="naver_blog", url="https://example.com/1", title="near 후기", snippet="방문"
    )
    store.link_place_evidence(
        place_id=place["id"], evidence_item_id=evidence["id"], match_type="exact",
        score=0.9, decision="matched",
    )

    coverage = zone_coverage(store, zone)

    assert haversine_meters(37.52, 126.86, 37.5201, 126.8601) < 1000
    assert coverage.inside_count == 1
    assert coverage.evidence_coverage == 1.0


def test_preference_profile_is_rebuilt_from_append_only_feedback(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    liked = seed_place(store, area["id"], "liked", "음식점 > 한식 > 고기")
    hidden = seed_place(store, area["id"], "hidden", "음식점 > 카페")
    store.record_user_feedback(feedback_key="1", domain="food", action="visit_confirmed", place_id=liked["id"])
    store.record_user_feedback(feedback_key="2", domain="food", action="hide", place_id=hidden["id"])
    store.record_user_feedback(feedback_key="3", domain="food", action="recommendation_shown", place_id=liked["id"])

    profile = build_preference_profile(store)
    snapshot = persist_preference_profile(store)

    assert profile["strong_signal_count"] == 2
    assert profile["category_scores"]["고기"] > 0
    assert profile["category_scores"]["카페"] < 0
    assert snapshot["evidence_count"] == 2


def test_offline_evaluation_uses_persisted_session_events(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="이태원", normalized_name="이태원")
    place = seed_place(store, area["id"], "selected")
    session = store.create_recommendation_session(domain="food", request_text="추천", area_id=area["id"])
    store.add_recommendation_candidate(
        session_id=session["id"], place_id=place["id"], rank=1, score=0.9,
        score_breakdown={"category": "한식"}, evidence_tier="verified",
    )
    store.record_user_feedback(
        feedback_key="visit", domain="food", action="visit_confirmed", place_id=place["id"],
        recommendation_session_id=session["id"],
    )

    metrics = evaluate_recommendations(store)

    assert metrics["selection_rate"] == 1.0
    assert metrics["mean_reciprocal_rank"] == 1.0
    assert metrics["session_count"] == 1


def test_collection_report_exposes_zero_baseline_for_pre_metric_runs(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    ledger = store.upsert_query_ledger_entry(
        domain="food", provider="kakao_local", query_text="신정동 맛집",
        area_id=area["id"], facet="broad_discovery",
    )
    store.record_query_ledger_result(ledger_id=ledger["id"], yielded_count=15)

    report = collection_report(store, days=30)

    assert report["runs"] == 1
    assert report["groups"][0]["novelty_rate"] == 0.0
