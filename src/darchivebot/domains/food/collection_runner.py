from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from darchivebot.domains.food.evidence_scoring import (
    blog_text_matches_name,
    normalized_evidence_score,
    score_blog_evidence,
)
from darchivebot.json_utils import loads_object
from darchivebot.models import QueryLedgerRecord
from darchivebot.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class CollectedPlace:
    provider_place_id: str
    name: str
    normalized_name: str
    category: str = ""
    address: str = ""
    road_address: str = ""
    phone: str = ""
    map_url: str = ""
    latitude: float | None = None
    longitude: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectedEvidence:
    url: str
    title: str
    snippet: str
    external_id: str = ""
    author: str = ""
    published_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class KakaoFoodCollectionPort(Protocol):
    @property
    def configured(self) -> bool: ...

    def search_places(self, *, query: str, page: int, sort_mode: str) -> list[CollectedPlace]: ...


class NaverFoodCollectionPort(Protocol):
    @property
    def configured(self) -> bool: ...

    def search_evidence(self, *, query: str, page: int, sort_mode: str) -> list[CollectedEvidence]: ...


@dataclass(frozen=True)
class FoodCollectionRunItem:
    ledger_id: str
    provider: str
    query_text: str
    status: str
    yielded_count: int = 0
    places_stored: int = 0
    evidence_stored: int = 0
    evidence_links: int = 0
    failure_reason: str = ""
    quota_cost: int = 0


@dataclass(frozen=True)
class FoodCollectionRun:
    items: tuple[FoodCollectionRunItem, ...]
    skipped_unconfigured: tuple[str, ...] = ()

    @property
    def quota_cost(self) -> int:
        return sum(item.quota_cost for item in self.items if item.status != "dry_run")


class FoodCollectionRunner:
    def __init__(
        self,
        store: PersonalContextRepositoryPort,
        *,
        kakao: KakaoFoodCollectionPort,
        naver: NaverFoodCollectionPort,
        provider_daily_limits: dict[str, int],
        now: datetime | None = None,
    ) -> None:
        self.store = store
        self.providers = {"kakao_local": kakao, "naver_blog": naver}
        self.provider_daily_limits = provider_daily_limits
        self.now = now or datetime.now(timezone.utc)

    def run_due(
        self,
        *,
        max_queries: int = 20,
        max_quota_cost: int = 20,
        dry_run: bool = False,
    ) -> FoodCollectionRun:
        due = self.store.list_due_query_ledger_entries(
            domain="food",
            due_at=self.now.isoformat(),
            limit=max(max_queries * 20, 200),
        )
        remaining_by_provider = {
            provider: max(
                0,
                limit
                - self.store.query_ledger_cost_since(
                    provider=provider,
                    since=self.now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                ),
            )
            for provider, limit in self.provider_daily_limits.items()
        }
        selected: list[QueryLedgerRecord] = []
        consumed = 0
        skipped_unconfigured: set[str] = set()
        for row in diversify_due_queries(due):
            provider = self.providers.get(row["provider"])
            if provider is None or not provider.configured:
                skipped_unconfigured.add(row["provider"])
                continue
            cost = int(row["quota_cost"])
            if cost > remaining_by_provider.get(row["provider"], 0):
                continue
            if consumed + cost > max_quota_cost:
                continue
            selected.append(row)
            consumed += cost
            remaining_by_provider[row["provider"]] -= cost
            if len(selected) >= max_queries:
                break

        items = tuple(self._execute(row, dry_run=dry_run) for row in selected)
        return FoodCollectionRun(items=items, skipped_unconfigured=tuple(sorted(skipped_unconfigured)))

    def _execute(self, row: QueryLedgerRecord, *, dry_run: bool) -> FoodCollectionRunItem:
        if dry_run:
            return FoodCollectionRunItem(
                ledger_id=row["id"],
                provider=row["provider"],
                query_text=row["query_text"],
                status="dry_run",
                quota_cost=int(row["quota_cost"]),
            )
        try:
            if row["provider"] == "kakao_local":
                item = self._collect_kakao(row)
            else:
                item = self._collect_naver(row)
            self.store.record_query_ledger_result(
                ledger_id=row["id"],
                yielded_count=item.yielded_count,
                next_run_at=(self.now + self._refresh_interval(row)).isoformat(),
            )
            return item
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"[:500]
            self.store.record_query_ledger_result(
                ledger_id=row["id"],
                yielded_count=0,
                failure_reason=reason,
                next_run_at=(self.now + timedelta(days=1)).isoformat(),
            )
            return FoodCollectionRunItem(
                ledger_id=row["id"],
                provider=row["provider"],
                query_text=row["query_text"],
                status="failed",
                failure_reason=reason,
                quota_cost=int(row["quota_cost"]),
            )

    def _collect_kakao(self, row: QueryLedgerRecord) -> FoodCollectionRunItem:
        places = self.providers["kakao_local"].search_places(
            query=row["query_text"],
            page=int(row["page"]),
            sort_mode=row["sort_mode"],
        )
        for place in places:
            self.store.upsert_place(
                provider="kakao_local",
                provider_place_id=place.provider_place_id,
                name=place.name,
                normalized_name=place.normalized_name,
                area_id=row["area_id"] or "",
                category=place.category,
                address=place.address,
                road_address=place.road_address,
                phone=place.phone,
                map_url=place.map_url,
                latitude=place.latitude,
                longitude=place.longitude,
                metadata={"query_text": row["query_text"], "raw": place.raw},
            )
        links = self._reconcile_area_evidence(row["area_id"] or "")
        return FoodCollectionRunItem(
            ledger_id=row["id"],
            provider=row["provider"],
            query_text=row["query_text"],
            status="completed",
            yielded_count=len(places),
            places_stored=len(places),
            evidence_links=links,
            quota_cost=int(row["quota_cost"]),
        )

    def _collect_naver(self, row: QueryLedgerRecord) -> FoodCollectionRunItem:
        evidence_items = self.providers["naver_blog"].search_evidence(
            query=row["query_text"],
            page=int(row["page"]),
            sort_mode=row["sort_mode"],
        )
        area = self.store.get_area(area_id=row["area_id"]) if row["area_id"] else None
        metadata = loads_object(row["metadata_json"] or "{}")
        area_name = area["name"] if area else str(metadata.get("area") or "")
        for evidence in evidence_items:
            score, signals, penalties = score_blog_evidence(
                title=evidence.title,
                snippet=evidence.snippet,
                published_at=evidence.published_at,
                area=area_name,
                query_text=row["query_text"],
            )
            self.store.upsert_evidence_item(
                provider="naver_blog",
                external_id=evidence.external_id,
                url=evidence.url,
                title=evidence.title,
                snippet=evidence.snippet,
                author=evidence.author,
                published_at=evidence.published_at,
                query_text=row["query_text"],
                raw={"provider": evidence.raw, "score": score, "signals": signals, "penalties": penalties},
                area_id=row["area_id"] or "",
            )
        links = self._reconcile_area_evidence(row["area_id"] or "")
        return FoodCollectionRunItem(
            ledger_id=row["id"],
            provider=row["provider"],
            query_text=row["query_text"],
            status="completed",
            yielded_count=len(evidence_items),
            evidence_stored=len(evidence_items),
            evidence_links=links,
            quota_cost=int(row["quota_cost"]),
        )

    def _reconcile_area_evidence(self, area_id: str) -> int:
        if not area_id:
            return 0
        places = self.store.list_places(area_id=area_id, limit=1000)
        evidence_items = self.store.list_evidence_items_for_area(
            area_id=area_id,
            provider="naver_blog",
            limit=5000,
        )
        existing_links = {
            (link["place_id"], link["evidence_item_id"])
            for link in self.store.list_place_evidence(place_ids=[place["id"] for place in places])
        }
        links = 0
        for evidence in evidence_items:
            evidence_text = f"{evidence['title']} {evidence['snippet']}"
            raw = loads_object(evidence["raw_json"] or "{}")
            score = int(raw.get("score") or 0)
            for place in places:
                if not blog_text_matches_name(place["name"], evidence_text):
                    continue
                self.store.link_place_evidence(
                    place_id=place["id"],
                    evidence_item_id=evidence["id"],
                    match_type="exact_or_token_name",
                    score=normalized_evidence_score(score),
                    decision="matched",
                    matched_terms=[place["name"]],
                )
                key = (place["id"], evidence["id"])
                if key not in existing_links:
                    links += 1
                    existing_links.add(key)
        return links

    @staticmethod
    def _refresh_interval(row: QueryLedgerRecord) -> timedelta:
        if row["facet"] in {"exploration", "broad_discovery"}:
            return timedelta(days=7)
        if row["facet"] == "evidence_refresh":
            return timedelta(days=14)
        return timedelta(days=30)


def diversify_due_queries(rows: list[QueryLedgerRecord]) -> list[QueryLedgerRecord]:
    remaining = list(enumerate(rows))
    provider_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    facet_counts: dict[str, int] = {}
    diversified: list[QueryLedgerRecord] = []
    while remaining:
        position = min(
            range(len(remaining)),
            key=lambda index: (
                provider_counts.get(remaining[index][1]["provider"], 0),
                area_counts.get(remaining[index][1]["area_id"] or "", 0),
                facet_counts.get(remaining[index][1]["facet"], 0),
                remaining[index][0],
            ),
        )
        _, row = remaining.pop(position)
        diversified.append(row)
        provider_counts[row["provider"]] = provider_counts.get(row["provider"], 0) + 1
        area_key = row["area_id"] or ""
        area_counts[area_key] = area_counts.get(area_key, 0) + 1
        facet_counts[row["facet"]] = facet_counts.get(row["facet"], 0) + 1
    return diversified
