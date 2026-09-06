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
        command=("dalife", "process", "--export-graph"),
        cadence="every_5_minutes",
        purpose="process pending captures and refresh derived graph outputs after successful work",
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
        cadence="every_5_minutes",
        purpose="send due SQLite-backed life reminders through Telegram",
        launchd_managed=False,
    ),
    ScheduledJob(
        name="feedback-replies",
        command=("dalife", "telegram"),
        cadence="keep_alive",
        purpose="handle Telegram callback feedback through the unified polling process",
        launchd_managed=False,
    ),
    ScheduledJob(
        name="revisit-digest",
        command=("dalife", "telegram-digest", "--kind", "revisit"),
        cadence="daily_09_00",
        purpose="suggest archive revisit candidates",
    ),
    ScheduledJob(
        name="project-seed-digest",
        command=("dalife", "telegram-digest", "--kind", "project-seed"),
        cadence="daily_18_00",
        purpose="suggest project seed candidates",
    ),
    ScheduledJob(
        name="weekly-insight",
        command=("dalife", "telegram-digest", "--kind", "weekly"),
        cadence="daily_09_30",
        purpose="prompt for weekly insight draft generation",
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


def launchd_schedule(*, include_life_sender: bool = False) -> tuple[ScheduledJob, ...]:
    return tuple(
        job
        for job in UNIFIED_SCHEDULE
        if job.enabled and (job.launchd_managed or (include_life_sender and job.name == "life-send"))
    )
