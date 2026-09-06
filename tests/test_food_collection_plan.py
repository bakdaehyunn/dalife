from __future__ import annotations

from dalife.domains.food import (
    FoodCollectionArea,
    FoodCollectionFacet,
    build_food_collection_plan,
    persist_food_collection_plan,
)
from dalife.storage import ArchiveStore


def test_food_collection_plan_respects_daily_quota_limit():
    plan = build_food_collection_plan(
        areas=[FoodCollectionArea("신정동"), FoodCollectionArea("이태원")],
        daily_quota_limit=5,
    )

    assert len(plan.queries) == 5
    assert plan.quota_cost == 5


def test_food_collection_plan_varies_provider_and_query_facets():
    plan = build_food_collection_plan(
        areas=[FoodCollectionArea("신정동", aliases=("목동역",))],
        daily_quota_limit=40,
    )

    providers = {query.provider for query in plan.queries}
    facets = {query.facet for query in plan.queries}
    query_texts = {query.query_text for query in plan.queries}

    assert providers == {"kakao_local", "naver_blog"}
    assert FoodCollectionFacet.BROAD_DISCOVERY in facets
    assert FoodCollectionFacet.CUISINE in facets
    assert FoodCollectionFacet.OCCASION in facets
    assert FoodCollectionFacet.EXPLORATION in facets
    assert "신정동 맛집" in query_texts
    assert "목동역 맛집 후기" in query_texts
    assert "신정동 혼밥 맛집" in query_texts


def test_food_collection_plan_deduplicates_alias_queries():
    plan = build_food_collection_plan(
        areas=[FoodCollectionArea("이태원", aliases=("이태원",))],
        daily_quota_limit=100,
    )
    keys = {(query.provider, query.query_text, query.sort_mode, query.page) for query in plan.queries}

    assert len(keys) == len(plan.queries)


def test_persist_food_collection_plan_writes_idempotent_query_ledger(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    plan = build_food_collection_plan(
        areas=[FoodCollectionArea("신정동")],
        daily_quota_limit=3,
    )

    first = persist_food_collection_plan(
        store,
        plan,
        area_ids_by_name={"신정동": area["id"]},
        next_run_at="2026-08-29T00:00:00+00:00",
    )
    second = persist_food_collection_plan(
        store,
        plan,
        area_ids_by_name={"신정동": area["id"]},
        next_run_at="2026-08-29T00:00:00+00:00",
    )
    due = store.list_due_query_ledger_entries(domain="food", due_at="2026-08-29T01:00:00+00:00")

    assert len(first) == 3
    assert [row["id"] for row in second] == [row["id"] for row in first]
    assert {row["id"] for row in due} == {row["id"] for row in first}
    assert {row["area_id"] for row in due} == {area["id"]}
