from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReminderCadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INTERVAL_DAYS = "interval_days"
    FIXED_DATES = "fixed_dates"


@dataclass(frozen=True)
class LifeReminder:
    reminder_id: str
    title: str
    cadence: ReminderCadence
    action: str
    time_of_day: str
    enabled: bool = True
    note: str = ""


@dataclass(frozen=True)
class LifeConfirmation:
    confirmation_id: str
    reminder_id: str
    status: str
    due_at: datetime
    answered_at: datetime | None = None

