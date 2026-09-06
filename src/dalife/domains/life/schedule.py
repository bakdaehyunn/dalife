from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dalife.domains.life.defaults import FixedReminderSpec, fixed_specs_by_kind, get_fixed_spec
from dalife.domains.life.messages import card
from dalife.domains.life.patterns import MessagePattern


WEEKDAYS = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}
WEEKDAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


@dataclass(frozen=True)
class ScheduledReminder:
    reminder_id: str
    scheduled_at: datetime
    title: str
    message: str

    @property
    def sent_key(self) -> str:
        return f"{self.reminder_id}:{self.scheduled_at.isoformat()}"


def due_reminders(
    now: datetime,
    config: dict[str, Any],
    window_minutes: int = 4,
    mac_status_text: str = "",
    pattern: MessagePattern | None = None,
) -> list[ScheduledReminder]:
    now = now.replace(second=0, microsecond=0)
    reminders = scheduled_reminders_near(now, config, mac_status_text=mac_status_text, pattern=pattern)
    return [reminder for reminder in reminders if abs(reminder.scheduled_at - now) <= timedelta(minutes=window_minutes)]


def scheduled_reminders_near(
    now: datetime,
    config: dict[str, Any],
    mac_status_text: str = "",
    pattern: MessagePattern | None = None,
) -> list[ScheduledReminder]:
    tz = now.tzinfo
    pattern = pattern or MessagePattern()
    items: list[ScheduledReminder] = []
    items.extend(haircut_reminders(now, config.get("haircut", {}), tz, pattern))
    items.extend(nail_reminders(now, config.get("nails", {}), tz, pattern))
    trash = trash_reminder(now, config.get("trash", {}), tz, pattern)
    if trash:
        items.append(trash)
    for spec in fixed_specs_by_kind("weekly"):
        default_note = mac_status_default_note(mac_status_text) if spec.reminder_id == "mac-status" else spec.default_note
        reminder = weekly_reminder(now, config.get(spec.config_section, {}), spec, default_note, tz, pattern)
        if reminder:
            items.append(reminder)
    for spec in fixed_specs_by_kind("interval"):
        reminder = interval_reminder(now, config.get(spec.config_section, {}), spec, tz, pattern)
        if reminder:
            items.append(reminder)
    items.extend(custom_reminders(now, config.get("custom", []), tz, pattern))
    return items


def upcoming_reminders(
    start: datetime,
    config: dict[str, Any],
    *,
    days: int,
    mac_status_text: str = "",
    pattern: MessagePattern | None = None,
) -> list[ScheduledReminder]:
    if days < 1:
        return []
    end = start + timedelta(days=days)
    by_key: dict[str, ScheduledReminder] = {}
    for offset in range(days + 1):
        probe = start + timedelta(days=offset)
        for reminder in scheduled_reminders_near(probe, config, mac_status_text=mac_status_text, pattern=pattern):
            if start <= reminder.scheduled_at < end:
                by_key[reminder.sent_key] = reminder
    return sorted(by_key.values(), key=lambda reminder: (reminder.scheduled_at, reminder.reminder_id))


def haircut_reminders(now: datetime, settings: dict[str, Any], tz: object, pattern: MessagePattern) -> list[ScheduledReminder]:
    spec = get_fixed_spec("haircut")
    if not settings.get("enabled", True):
        return []
    base = parse_date(str(settings.get("base_date", "2026-05-10")))
    interval_months = int(settings.get("interval_months", 1))
    notify = parse_time(str(settings.get("notify_time", "08:45")))
    reminders: list[ScheduledReminder] = []
    for step in range(interval_months, interval_months * 61, interval_months):
        candidate = add_months(base, step)
        haircut_day = apply_haircut_weekend_policy(candidate, str(settings.get("weekend_policy", "previous_sunday")))
        notify_day = haircut_day - timedelta(days=haircut_day.weekday())
        if abs((notify_day - now.date()).days) > 1:
            continue
        scheduled = datetime.combine(notify_day, notify, tzinfo=tz)
        reminders.append(
            ScheduledReminder(
                reminder_id=f"haircut-booking-{haircut_day.isoformat()}",
                scheduled_at=scheduled,
                title=str(settings.get("title") or spec.title),
                message=card(
                    str(settings.get("title") or spec.title),
                    f"{format_date_ko(haircut_day)} 헤어컷 예정",
                    str(settings.get("action") or spec.default_action),
                    str(settings.get("note") or spec.default_note),
                    pattern,
                ),
            )
        )
    return reminders


def nail_reminders(now: datetime, settings: dict[str, Any], tz: object, pattern: MessagePattern) -> list[ScheduledReminder]:
    if not settings.get("enabled", True):
        return []
    base = parse_date(str(settings.get("base_date", "2026-05-10")))
    notify = parse_time(str(settings.get("notify_time", "20:00")))
    scheduled = datetime.combine(now.date(), notify, tzinfo=tz)
    reminders: list[ScheduledReminder] = []
    days_since = (now.date() - base).days
    fingernails_days = int(settings.get("fingernails_days", 7))
    toenails_days = int(settings.get("toenails_days", 21))
    if settings.get("fingernails_enabled", True) and days_since >= 0 and days_since % fingernails_days == 0:
        spec = get_fixed_spec("fingernails")
        title = str(settings.get("fingernails_title") or spec.title)
        reminders.append(ScheduledReminder(spec.reminder_id, scheduled, title, card(title, f"손톱 {fingernails_days}일 주기", str(settings.get("fingernails_action") or spec.default_action), str(settings.get("fingernails_note") or spec.default_note), pattern)))
    if settings.get("toenails_enabled", True) and days_since >= 0 and days_since % toenails_days == 0:
        spec = get_fixed_spec("toenails")
        title = str(settings.get("toenails_title") or spec.title)
        reminders.append(ScheduledReminder(spec.reminder_id, scheduled, title, card(title, f"발톱 {toenails_days}일 주기", str(settings.get("toenails_action") or spec.default_action), str(settings.get("toenails_note") or spec.default_note), pattern)))
    return reminders


def trash_reminder(now: datetime, settings: dict[str, Any], tz: object, pattern: MessagePattern) -> ScheduledReminder | None:
    spec = get_fixed_spec("trash")
    if not settings.get("enabled", True):
        return None
    weekdays = {WEEKDAYS[item] for item in settings.get("weekdays", ["tue", "thu", "sun"])}
    if now.weekday() not in weekdays:
        return None
    scheduled = datetime.combine(now.date(), parse_time(str(settings.get("notify_time", "20:00"))), tzinfo=tz)
    title = str(settings.get("title") or spec.title)
    return ScheduledReminder(
        f"trash-{now.date().isoformat()}",
        scheduled,
        title,
        card(title, f"{format_date_ko(now.date())} {scheduled:%H:%M}", str(settings.get("action") or spec.default_action), str(settings.get("note") or spec.default_note), pattern),
    )


def weekly_reminder(
    now: datetime,
    settings: dict[str, Any],
    spec: FixedReminderSpec,
    default_note: str,
    tz: object,
    pattern: MessagePattern,
) -> ScheduledReminder | None:
    if not settings.get("enabled", True):
        return None
    weekday = WEEKDAYS[str(settings.get("weekday", "sat"))]
    if now.weekday() != weekday:
        return None
    scheduled = datetime.combine(now.date(), parse_time(str(settings.get("notify_time", "10:00"))), tzinfo=tz)
    title = str(settings.get("title") or spec.title)
    return ScheduledReminder(
        f"{spec.reminder_id}-{now.date().isoformat()}",
        scheduled,
        title,
        card(title, f"{format_date_ko(now.date())} {scheduled:%H:%M}", str(settings.get("action") or spec.default_action), str(settings.get("note") or default_note), pattern),
    )


def interval_reminder(
    now: datetime,
    settings: dict[str, Any],
    spec: FixedReminderSpec,
    tz: object,
    pattern: MessagePattern,
) -> ScheduledReminder | None:
    if not settings.get("enabled", True):
        return None
    base = parse_date(str(settings.get("base_date", "2026-05-10")))
    days = int(settings.get("days", 14))
    if days < 1:
        return None
    days_since = (now.date() - base).days
    if days_since < 0 or days_since % days != 0:
        return None
    scheduled = datetime.combine(now.date(), parse_time(str(settings.get("notify_time", "11:00"))), tzinfo=tz)
    title = str(settings.get("title") or spec.title)
    return ScheduledReminder(
        f"{spec.reminder_id}-{now.date().isoformat()}",
        scheduled,
        title,
        card(title, f"{days}일 주기, {format_date_ko(now.date())} {scheduled:%H:%M}", str(settings.get("action") or spec.default_action), str(settings.get("note") or spec.default_note), pattern),
    )


def mac_status_default_note(status_text: str) -> str:
    lines = [status_text] if status_text else ["상태 수집 결과가 없습니다."]
    lines.extend(get_fixed_spec("mac-status").default_note.splitlines())
    return "\n".join(lines)


def custom_reminders(
    now: datetime,
    records: object,
    tz: object,
    pattern: MessagePattern,
) -> list[ScheduledReminder]:
    if not isinstance(records, list):
        return []
    reminders: list[ScheduledReminder] = []
    for record in records:
        if not isinstance(record, dict) or not record.get("enabled", True):
            continue
        kind = str(record.get("kind", ""))
        scheduled = custom_scheduled_at(now, record, kind, tz)
        if scheduled is None:
            continue
        title = str(record.get("title") or record.get("id"))
        reminders.append(
            ScheduledReminder(
                reminder_id=str(record["id"]),
                scheduled_at=scheduled,
                title=title,
                message=card(
                    title,
                    custom_schedule_text(now, record, kind, scheduled),
                    str(record.get("action") or title),
                    str(record.get("note") or ""),
                    pattern,
                ),
            )
        )
    return reminders


def custom_scheduled_at(
    now: datetime,
    record: dict[str, Any],
    kind: str,
    tz: object,
) -> datetime | None:
    notify = parse_time(str(record.get("time", "00:00")))
    if kind == "one-off":
        target = parse_date(str(record.get("date")))
        return datetime.combine(target, notify, tzinfo=tz) if target == now.date() else None
    if kind == "weekly":
        weekday = WEEKDAYS[str(record.get("weekday"))]
        return datetime.combine(now.date(), notify, tzinfo=tz) if now.weekday() == weekday else None
    if kind == "interval":
        base = parse_date(str(record.get("base_date")))
        days = int(record.get("days", 1))
        elapsed = (now.date() - base).days
        if days < 1 or elapsed < 0 or elapsed % days != 0:
            return None
        return datetime.combine(now.date(), notify, tzinfo=tz)
    return None


def custom_schedule_text(
    now: datetime,
    record: dict[str, Any],
    kind: str,
    scheduled: datetime,
) -> str:
    if kind == "one-off":
        return f"{format_date_ko(scheduled.date())} {scheduled:%H:%M}"
    if kind == "weekly":
        return f"매주 {WEEKDAY_KO[scheduled.weekday()]} {scheduled:%H:%M}"
    if kind == "interval":
        return f"{record.get('days')}일마다 {scheduled:%H:%M}"
    return f"{format_date_ko(now.date())} {scheduled:%H:%M}"


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def apply_haircut_weekend_policy(value: date, policy: str) -> date:
    if policy != "previous_sunday":
        raise ValueError(f"unsupported haircut weekend_policy: {policy}")
    if value.weekday() <= 4:
        return value - timedelta(days=value.weekday() + 1)
    return value


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str) -> time:
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def format_date_ko(value: date) -> str:
    return f"{value.month}월 {value.day}일 {WEEKDAY_KO[value.weekday()]}"


def kst_datetime(date_text: str, time_text: str, timezone: str = "Asia/Seoul") -> datetime:
    return datetime.combine(parse_date(date_text), parse_time(time_text), tzinfo=ZoneInfo(timezone))
