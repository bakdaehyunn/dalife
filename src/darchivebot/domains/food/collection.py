from __future__ import annotations

from darchivebot.domains.food.collection_plan import FoodCollectionPlan
from darchivebot.models import QueryLedgerRecord
from darchivebot.ports import PersonalContextRepositoryPort


def persist_food_collection_plan(
    store: PersonalContextRepositoryPort,
    plan: FoodCollectionPlan,
    *,
    area_ids_by_name: dict[str, str] | None = None,
    next_run_at: str = "",
) -> list[QueryLedgerRecord]:
    area_ids_by_name = area_ids_by_name or {}
    entries: list[QueryLedgerRecord] = []
    for query in plan.queries:
        entries.append(
            store.upsert_query_ledger_entry(
                domain="food",
                provider=query.provider,
                query_text=query.query_text,
                area_id=area_ids_by_name.get(query.area, ""),
                facet=query.facet.value,
                sort_mode=query.sort_mode,
                page=query.page,
                quota_cost=query.quota_cost,
                next_run_at=next_run_at,
                metadata={"area": query.area},
            )
        )
    return entries
