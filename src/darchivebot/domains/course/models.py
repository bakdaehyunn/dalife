from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CourseStop:
    stop_id: str
    title: str
    source_domain: str
    reason: str
    starts_at: datetime | None = None
    evidence_refs: tuple[str, ...] = ()
    place_id: str = ""
    reminder_event_id: str = ""
    archive_item_id: str = ""


@dataclass(frozen=True)
class CoursePlan:
    plan_id: str
    title: str
    generated_at: datetime
    stops: tuple[CourseStop, ...]
    context: str = ""
    area_id: str = ""
