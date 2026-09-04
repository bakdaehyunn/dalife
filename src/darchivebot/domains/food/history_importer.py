from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from itertools import groupby
from typing import Any, Iterable

from darchivebot.ports import PersonalContextRepositoryPort
from darchivebot.domains.food.collection_plan import (
    FoodCollectionFacet,
    FoodCollectionPlan,
    FoodCollectionQuery,
)


MOMUK_HISTORY_IMPORT_KEY = "migration.momuk.recommendation_history"


@dataclass(frozen=True)
class MomukHistoryImportReport:
    source_rows: int
    imported_rows: int
    skipped_rows: int
    sessions: int
    candidates: int
    linked_places: int
    dry_run: bool


def import_momuk_history(
    store: PersonalContextRepositoryPort,
    rows: Iterable[dict[str, Any]],
    *,
    dry_run: bool,
) -> MomukHistoryImportReport:
    source_rows = list(rows)
    state = store.get_app_setting(setting_key=MOMUK_HISTORY_IMPORT_KEY) or {}
    imported_ids = {str(value) for value in state.get("row_ids", [])}
    pending = [row for row in source_rows if str(row["id"]) not in imported_ids]

    places_by_name: dict[str, list[Any]] = {}
    for place in store.list_places(limit=100_000):
        places_by_name.setdefault(_normalize(str(place["name"])), []).append(place)

    sessions = candidates = linked_places = 0
    ordered = sorted(pending, key=_group_key)
    for _, grouped in groupby(ordered, key=_group_key):
        items = list(grouped)
        first = items[0]
        sessions += 1
        if dry_run:
            session_id = ""
        else:
            session = store.create_recommendation_session(
                domain="food",
                request_text=str(first.get("request_text") or ""),
                status="completed",
                context={
                    "source": "momukbot",
                    "legacy_chat_id": str(first.get("chat_id") or ""),
                    "area": str(first.get("area") or ""),
                    "topic": str(first.get("topic") or ""),
                    "search_keyword": str(first.get("search_keyword") or ""),
                    "legacy_created_at": str(first.get("created_at") or ""),
                    "legacy_row_ids": [str(item["id"]) for item in items],
                },
                completed_at=str(first.get("created_at") or ""),
            )
            session_id = str(session["id"])
        for rank, item in enumerate(items, start=1):
            candidates += 1
            matches = places_by_name.get(_normalize(str(item.get("place_name") or "")), [])
            place_id = str(matches[0]["id"]) if len(matches) == 1 else ""
            linked_places += bool(place_id)
            if not dry_run:
                store.add_recommendation_candidate(
                    session_id=session_id,
                    place_id=place_id,
                    rank=rank,
                    score=0.0,
                    evidence_tier="legacy",
                    explanation=str(item.get("reason") or ""),
                    score_breakdown={
                        "source": "momukbot",
                        "legacy_row_id": str(item["id"]),
                        "place_name": str(item.get("place_name") or ""),
                        "category": str(item.get("category") or ""),
                        "status_marker": str(item.get("status_marker") or ""),
                        "links": _links(item.get("links_json")),
                    },
                )

    if not dry_run and pending:
        imported_ids.update(str(row["id"]) for row in pending)
        store.set_app_setting(
            setting_key=MOMUK_HISTORY_IMPORT_KEY,
            value={"row_ids": sorted(imported_ids)},
        )
    return MomukHistoryImportReport(
        source_rows=len(source_rows),
        imported_rows=len(pending),
        skipped_rows=len(source_rows) - len(pending),
        sessions=sessions,
        candidates=candidates,
        linked_places=int(linked_places),
        dry_run=dry_run,
    )


def build_momuk_history_refresh_plan(
    store: PersonalContextRepositoryPort,
    *,
    area: str,
    legacy_areas: tuple[str, ...] = (),
    place_limit: int = 20,
) -> FoodCollectionPlan:
    accepted_areas = {area, *legacy_areas}
    counts: Counter[str] = Counter()
    for session in store.list_recommendation_sessions(domain="food", limit=10_000):
        context = _object_json(session["context_json"])
        if context.get("source") != "momukbot" or str(context.get("area") or "") not in accepted_areas:
            continue
        seen_in_session: set[str] = set()
        for candidate in store.list_recommendation_candidates(session_id=str(session["id"])):
            if candidate["place_id"]:
                continue
            details = _object_json(candidate["score_breakdown_json"])
            name = str(details.get("place_name") or "").strip()
            if name and name not in seen_in_session:
                counts[name] += 1
                seen_in_session.add(name)

    ranked_names = [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:place_limit]]
    queries: list[FoodCollectionQuery] = []
    for name in ranked_names:
        queries.extend(
            (
                FoodCollectionQuery(
                    provider="kakao_local",
                    query_text=f"{area} {name}",
                    area=area,
                    facet=FoodCollectionFacet.EVIDENCE_REFRESH,
                    sort_mode="accuracy",
                ),
                FoodCollectionQuery(
                    provider="naver_blog",
                    query_text=f'"{name}" {area} 후기',
                    area=area,
                    facet=FoodCollectionFacet.EVIDENCE_REFRESH,
                    sort_mode="date",
                ),
            )
        )
    return FoodCollectionPlan(daily_quota_limit=len(queries), queries=tuple(queries))


def _group_key(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(row.get(key) or "")
        for key in ("created_at", "chat_id", "request_text", "area", "topic", "search_keyword")
    )


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def _links(value: Any) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _object_json(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
