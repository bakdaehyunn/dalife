from __future__ import annotations

from datetime import datetime, timezone

from dalife.domains.food import (
    CollectedEvidence,
    CollectedPlace,
    FoodCollectionRunner,
    diversify_due_queries,
)
from dalife.storage import ArchiveStore


class FakeKakao:
    configured = True

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def search_places(self, *, query: str, page: int, sort_mode: str):
        self.calls.append((query, page, sort_mode))
        if self.fail:
            raise RuntimeError("kakao unavailable")
        return [
            CollectedPlace(
                provider_place_id="20551759",
                name="미성참숯정육식당",
                normalized_name="미성참숯정육식당",
                category="음식점 > 한식 > 육류",
                road_address="서울 양천구 신정중앙로 70",
                map_url="https://place.map.kakao.com/20551759",
                latitude=37.52,
                longitude=126.86,
                raw={"id": "20551759"},
            )
        ]


class FakeNaver:
    configured = True

    def __init__(self) -> None:
        self.calls = []

    def search_evidence(self, *, query: str, page: int, sort_mode: str):
        self.calls.append((query, page, sort_mode))
        return [
            CollectedEvidence(
                url="https://blog.naver.com/local/1",
                title="신정동 미성참숯정육식당 방문 후기",
                snippet="직접 다녀왔고 고기를 주문했습니다",
                author="local-author",
                published_at="20260820",
                raw={"postdate": "20260820"},
            ),
            CollectedEvidence(
                url="https://blog.naver.com/local/2",
                title="신정동 다른 식당 후기",
                snippet="다른 곳 방문",
                author="another-author",
                published_at="20260819",
            ),
        ]


def _seed_ledger(store):
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    kakao = store.upsert_query_ledger_entry(
        domain="food",
        provider="kakao_local",
        query_text="신정동 고기",
        area_id=area["id"],
        facet="cuisine",
        sort_mode="accuracy",
        page=1,
    )
    naver = store.upsert_query_ledger_entry(
        domain="food",
        provider="naver_blog",
        query_text="신정동 고기 후기",
        area_id=area["id"],
        facet="evidence_refresh",
        sort_mode="date",
        page=1,
        metadata={"area": "신정동"},
    )
    return area, kakao, naver


def _runner(store, kakao=None, naver=None):
    return FoodCollectionRunner(
        store,
        kakao=kakao or FakeKakao(),
        naver=naver or FakeNaver(),
        provider_daily_limits={"kakao_local": 10, "naver_blog": 10},
        now=datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc),
    )


def test_collection_runner_stores_places_all_evidence_and_matching_links(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area, _, _ = _seed_ledger(store)

    run = _runner(store).run_due(max_queries=2, max_quota_cost=2)

    assert [item.status for item in run.items] == ["completed", "completed"]
    assert run.items[0].places_stored == 1
    assert run.items[1].evidence_stored == 2
    assert run.items[1].evidence_links == 1
    places = store.list_places(area_id=area["id"])
    evidence = store.list_evidence_items(
        evidence_item_ids=[row["id"] for row in _all_rows(store, "evidence_items")]
    )
    links = store.list_place_evidence(place_ids=[places[0]["id"]])
    assert places[0]["name"] == "미성참숯정육식당"
    assert len(evidence) == 2
    assert len(links) == 1
    assert links[0]["score"] > 0.7


def test_collection_runner_isolates_failure_and_records_backoff(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _, kakao_row, _ = _seed_ledger(store)

    run = _runner(store, kakao=FakeKakao(fail=True)).run_due(max_queries=2, max_quota_cost=2)

    assert [item.status for item in run.items] == ["failed", "completed"]
    with store.connect() as conn:
        failed = conn.execute("SELECT * FROM query_ledger WHERE id = ?", (kakao_row["id"],)).fetchone()
    assert "kakao unavailable" in failed["failure_reason"]
    assert failed["next_run_at"] == "2026-08-30T01:00:00+00:00"


def test_collection_runner_dry_run_and_daily_limit_do_not_call_providers(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_ledger(store)
    kakao = FakeKakao()
    naver = FakeNaver()
    runner = _runner(store, kakao=kakao, naver=naver)

    dry_run = runner.run_due(max_queries=1, max_quota_cost=1, dry_run=True)

    assert [item.status for item in dry_run.items] == ["dry_run"]
    assert kakao.calls == []
    assert naver.calls == []
    assert _all_rows(store, "places") == []

    limited = FoodCollectionRunner(
        store,
        kakao=kakao,
        naver=naver,
        provider_daily_limits={"kakao_local": 0, "naver_blog": 0},
        now=datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc),
    ).run_due(max_queries=2, max_quota_cost=2)
    assert limited.items == ()


def test_collection_runner_skips_unconfigured_provider_without_marking_query_failed(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_ledger(store)
    unconfigured = FakeNaver()
    unconfigured.configured = False

    run = _runner(store, naver=unconfigured).run_due(max_queries=2, max_quota_cost=2)

    assert len(run.items) == 1
    assert run.skipped_unconfigured == ("naver_blog",)


def test_due_query_diversification_balances_provider_area_and_facet(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    first_area, _, _ = _seed_ledger(store)
    second_area = store.upsert_area(name="이태원", normalized_name="이태원")
    for index in range(3):
        store.upsert_query_ledger_entry(
            domain="food",
            provider="kakao_local",
            query_text=f"신정동 추가 {index}",
            area_id=first_area["id"],
            facet="cuisine",
            sort_mode="accuracy",
        )
    store.upsert_query_ledger_entry(
        domain="food",
        provider="naver_blog",
        query_text="이태원 데이트 맛집",
        area_id=second_area["id"],
        facet="occasion",
        sort_mode="sim",
    )
    rows = store.list_due_query_ledger_entries(domain="food", due_at="2999-01-01T00:00:00+00:00")

    first_four = diversify_due_queries(rows)[:4]

    assert {row["provider"] for row in first_four} == {"kakao_local", "naver_blog"}
    assert {row["area_id"] for row in first_four} == {first_area["id"], second_area["id"]}
    assert len({row["facet"] for row in first_four}) >= 2


def test_later_kakao_discovery_reconciles_evidence_collected_first(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area, _, _ = _seed_ledger(store)
    now = datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc)

    naver_first = FoodCollectionRunner(
        store,
        kakao=FakeKakao(),
        naver=FakeNaver(),
        provider_daily_limits={"kakao_local": 0, "naver_blog": 10},
        now=now,
    ).run_due(max_queries=1, max_quota_cost=1)
    assert naver_first.items[0].provider == "naver_blog"
    assert naver_first.items[0].evidence_links == 0

    kakao_later = FoodCollectionRunner(
        store,
        kakao=FakeKakao(),
        naver=FakeNaver(),
        provider_daily_limits={"kakao_local": 10, "naver_blog": 0},
        now=now,
    ).run_due(max_queries=1, max_quota_cost=1)

    assert kakao_later.items[0].provider == "kakao_local"
    assert kakao_later.items[0].evidence_links == 1
    places = store.list_places(area_id=area["id"])
    assert len(store.list_place_evidence(place_ids=[places[0]["id"]])) == 1


def _all_rows(store, table: str):
    with store.connect() as conn:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
