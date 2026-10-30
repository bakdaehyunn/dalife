from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    command: tuple[str, ...]
    cadence: str
    purpose: str
    enabled: bool = True
    launchd_managed: bool = True


UNIFIED_SCHEDULE: tuple[ScheduledJob, ...] = (
    ScheduledJob(
        name="telegram",
        command=("dalife", "telegram"),
        cadence="keep_alive",
        purpose="poll Telegram updates for archive capture and future personal-domain intents",
    ),
    ScheduledJob(
        name="archive-process",
        command=("dalife", "archive", "process"),
        cadence="every_15_minutes",
        purpose="process pending captures into searchable SQLite archive data",
    ),
    ScheduledJob(
        name="food-collect",
        command=("dalife", "food", "run-collection", "--max-queries", "20", "--max-quota-cost", "20"),
        cadence="daily_03_00",
        purpose="run due food collection queries without exceeding provider quota budgets",
    ),
    ScheduledJob(
        name="life-send",
        command=("dalife", "life", "run-once"),
        cadence="every_15_minutes",
        purpose="send due life reminders and restaurant visit confirmations through Telegram",
    ),
    ScheduledJob(
        name="course-suggestions",
        command=("dalife", "course", "plan"),
        cadence="daily_evening",
        purpose="prepare personal course suggestions after enough food/life/archive data exists",
        enabled=False,
        launchd_managed=False,
    ),
)


def unified_schedule() -> tuple[ScheduledJob, ...]:
    return UNIFIED_SCHEDULE


def schedule_summary(*, include_disabled: bool = False) -> list[dict[str, object]]:
    return [
        {
            "name": job.name,
            "command": list(job.command),
            "cadence": job.cadence,
            "purpose": job.purpose,
            "enabled": job.enabled,
            "launchd_managed": job.launchd_managed,
        }
        for job in UNIFIED_SCHEDULE
        if include_disabled or job.enabled
    ]


def launchd_schedule() -> tuple[ScheduledJob, ...]:
    return tuple(job for job in UNIFIED_SCHEDULE if job.enabled and job.launchd_managed)
