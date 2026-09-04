from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from darchivebot.domains.course.models import CoursePlan, CourseStop
from darchivebot.domains.food.ranking import RankedFoodPlace
from darchivebot.models import ArchiveItemRecord, CoursePlanRecord, ReminderEventRecord
from darchivebot.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class CoursePlanningContext:
    title: str
    generated_at: datetime
    area_id: str = ""
    intent: str = ""


def compose_course_plan(
    *,
    context: CoursePlanningContext,
    food_candidates: list[RankedFoodPlace],
    due_life_events: list[ReminderEventRecord],
    archive_items: list[ArchiveItemRecord],
    max_stops: int = 4,
) -> CoursePlan:
    stops: list[CourseStop] = []
    cursor = context.generated_at

    if due_life_events:
        event = due_life_events[0]
        payload = _json_object(event["response_payload_json"])
        stops.append(
            CourseStop(
                stop_id=f"life:{event['id']}",
                title=str(payload.get("title") or event["event_key"]),
                source_domain="life",
                reason="지금 처리할 생활 일정을 코스 시작에 함께 배치했습니다.",
                starts_at=cursor,
                reminder_event_id=str(event["id"]),
                evidence_refs=(f"reminder_event:{event['id']}",),
            )
        )
        cursor += timedelta(minutes=30)

    # Multiple restaurants are alternatives, not sequential course stops.
    for ranked in food_candidates[: min(1, max(0, max_stops - len(stops)))]:
        place = ranked.place
        stops.append(
            CourseStop(
                stop_id=f"food:{place.provider}:{place.provider_place_id}",
                title=place.name,
                source_domain="food",
                reason=f"저장된 장소 근거와 개인 적합도 점수 {ranked.score:.2f}를 반영했습니다.",
                starts_at=cursor,
                place_id=place.place_id,
                evidence_refs=tuple(item.url for item in place.evidence if item.url),
            )
        )
        cursor += timedelta(hours=1)

    if archive_items and len(stops) < max_stops:
        item = archive_items[0]
        stops.append(
            CourseStop(
                stop_id=f"archive:{item['id']}",
                title=str(item["title"]),
                source_domain="archive",
                reason="저장해 둔 관심 항목을 코스에서 다시 확인할 수 있게 연결했습니다.",
                starts_at=cursor,
                archive_item_id=str(item["id"]),
                evidence_refs=(f"archive_item:{item['id']}",),
            )
        )

    return CoursePlan(
        plan_id="",
        title=context.title,
        generated_at=context.generated_at,
        stops=tuple(stops),
        context=context.intent,
        area_id=context.area_id,
    )


def persist_course_plan(
    store: PersonalContextRepositoryPort,
    plan: CoursePlan,
) -> CoursePlanRecord:
    stored = store.create_course_plan(
        title=plan.title,
        area_id=plan.area_id,
        context={"intent": plan.context},
        generated_at=plan.generated_at.isoformat(),
    )
    for index, stop in enumerate(plan.stops, start=1):
        store.add_course_plan_stop(
            course_plan_id=stored["id"],
            stop_order=index,
            source_domain=stop.source_domain,
            title=stop.title,
            reason=stop.reason,
            place_id=stop.place_id,
            reminder_event_id=stop.reminder_event_id,
            archive_item_id=stop.archive_item_id,
            starts_at=stop.starts_at.isoformat() if stop.starts_at else "",
            evidence_refs=list(stop.evidence_refs),
        )
    return stored


def _json_object(raw):
    if isinstance(raw, str):
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    return dict(raw) if isinstance(raw, dict) else {}
