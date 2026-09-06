from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from dalife.domains.course.models import CoursePlan
from dalife.domains.course.planner import (
    CoursePlanningContext,
    compose_course_plan,
    persist_course_plan,
)
from dalife.domains.food import FoodRecommendationContext, recommend_local_food
from dalife.models import AreaRecord, CoursePlanRecord
from dalife.ports import PersonalContextRepositoryPort, SearchRepositoryPort


class CourseContextStore(PersonalContextRepositoryPort, SearchRepositoryPort, Protocol):
    pass


@dataclass(frozen=True)
class LocalCourseResult:
    area: AreaRecord | None
    plan: CoursePlan
    stored: CoursePlanRecord | None = None


def plan_local_course(
    store: CourseContextStore,
    *,
    title: str,
    area_name: str,
    generated_at: datetime,
    intent: str,
    persist: bool = False,
    max_stops: int = 4,
) -> LocalCourseResult:
    area = store.get_area_by_normalized_name(normalized_name=_normalize(area_name))
    food = recommend_local_food(
        store,
        request_text=intent,
        context=FoodRecommendationContext(
            area=area_name,
            topic=intent,
            occasion=intent,
            count=max_stops,
        ),
        persist_session=False,
    )
    due_events = store.list_due_reminder_events(
        due_at=generated_at.isoformat(),
        status="pending",
        limit=max_stops,
    )
    archive_items = _archive_context(store, area_name, intent, max_stops)
    plan = compose_course_plan(
        context=CoursePlanningContext(
            title=title,
            generated_at=generated_at,
            area_id=str(area["id"]) if area is not None else "",
            intent=intent,
        ),
        food_candidates=list(food.ranked_places),
        due_life_events=due_events,
        archive_items=archive_items,
        max_stops=max_stops,
    )
    stored = persist_course_plan(store, plan) if persist else None
    return LocalCourseResult(area=area, plan=plan, stored=stored)


def match_course_area(store: PersonalContextRepositoryPort, text: str) -> AreaRecord | None:
    compact = _normalize(text)
    matches = [area for area in store.list_areas() if _normalize(str(area["name"])) in compact]
    return max(matches, key=lambda area: len(_normalize(str(area["name"])))) if matches else None


def _archive_context(
    store: SearchRepositoryPort,
    area_name: str,
    intent: str,
    limit: int,
):
    queries = [value for value in (f"{area_name} {intent}".strip(), area_name, intent) if value]
    seen: set[str] = set()
    rows = []
    for query in queries:
        for row in store.search_archive(query, limit=limit):
            if row["id"] not in seen:
                seen.add(str(row["id"]))
                rows.append(row)
                if len(rows) >= limit:
                    return rows
    return rows


def _normalize(value: str) -> str:
    return "".join(character.lower() for character in value if not character.isspace())
