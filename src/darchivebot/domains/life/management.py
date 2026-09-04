from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from darchivebot.domains.life.defaults import FIXED_REMINDERS
from darchivebot.models import ReminderRecord
from darchivebot.models import ReminderEventRecord
from darchivebot.ports import PersonalContextRepositoryPort


WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
CUSTOM_KINDS = {"one-off", "weekly", "interval"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class LifeValidationError(ValueError):
    pass


def reminder_details(row: ReminderRecord) -> dict[str, Any]:
    schedule = _schedule(row)
    return {
        "id": str(row["reminder_key"]),
        "type": "fixed" if row["reminder_key"] in FIXED_REMINDERS else "custom",
        "title": str(row["title"]),
        "kind": str(row["cadence"]),
        "action": str(row["action"]),
        "note": str(row["note"]),
        "enabled": bool(row["enabled"]),
        "requires_confirmation": bool(row["requires_confirmation"]),
        **schedule,
    }


def reminder_event_details(row: ReminderEventRecord) -> dict[str, Any]:
    payload = json.loads(str(row["response_payload_json"] or "{}"))
    payload = payload if isinstance(payload, dict) else {}
    return {
        "id": str(row["id"]),
        "event_key": str(row["event_key"]),
        "due_at": str(row["due_at"]),
        "status": str(row["status"]),
        "title": str(payload.get("title") or ""),
        "selected_response": payload.get("selected_response") or payload.get("last_answer"),
        "responded_at": str(row["responded_at"] or ""),
        "sent_at": str(row["sent_at"] or ""),
    }


def set_reminder_enabled(
    store: PersonalContextRepositoryPort,
    reminder_id: str,
    enabled: bool,
) -> ReminderRecord:
    row = _required(store, reminder_id)
    return _save(store, row, enabled=enabled)


def add_custom_reminder(
    store: PersonalContextRepositoryPort,
    values: dict[str, Any],
) -> ReminderRecord:
    validate_custom(values)
    reminder_id = str(values["id"])
    if store.get_reminder_by_key(reminder_key=reminder_id) is not None:
        raise LifeValidationError(f"duplicate reminder id: {reminder_id}")
    routine = store.upsert_routine(
        routine_key=reminder_id,
        title=str(values["title"]),
        description=str(values.get("note") or ""),
        metadata={"source": "darchivebot", "type": "custom"},
    )
    schedule = {
        key: values[key]
        for key in ("time", "date", "weekday", "base_date", "days")
        if values.get(key) is not None
    }
    return store.upsert_reminder(
        routine_id=str(routine["id"]),
        reminder_key=reminder_id,
        title=str(values["title"]).strip(),
        cadence=str(values["kind"]),
        schedule=schedule,
        action=str(values["action"]).strip(),
        note=str(values.get("note") or ""),
        enabled=True,
    )


def update_reminder(
    store: PersonalContextRepositoryPort,
    reminder_id: str,
    values: dict[str, Any],
) -> ReminderRecord:
    row = _required(store, reminder_id)
    updates = {key: value for key, value in values.items() if value is not None}
    if not updates:
        raise LifeValidationError("at least one update field is required")
    if reminder_id in FIXED_REMINDERS:
        _validate_fixed_update(reminder_id, updates)
    schedule = _schedule(row)
    for key in ("time", "date", "weekday", "base_date", "days"):
        if key in updates:
            schedule[key] = updates.pop(key)
    candidate = reminder_details(row) | updates | schedule
    if reminder_id not in FIXED_REMINDERS:
        validate_custom(candidate)
    return _save(
        store,
        row,
        title=str(updates.get("title", row["title"])),
        action=str(updates.get("action", row["action"])),
        note=str(updates.get("note", row["note"])),
        schedule=schedule,
    )


def remove_custom_reminder(store: PersonalContextRepositoryPort, reminder_id: str) -> None:
    _required(store, reminder_id)
    if reminder_id in FIXED_REMINDERS:
        raise LifeValidationError(f"cannot remove fixed reminder: {reminder_id}")
    if not store.delete_reminder(reminder_key=reminder_id):
        raise LifeValidationError(f"unknown reminder: {reminder_id}")


def validate_stored_reminders(store: PersonalContextRepositoryPort) -> list[str]:
    errors: list[str] = []
    for row in store.list_reminders():
        reminder_id = str(row["reminder_key"])
        try:
            if reminder_id in FIXED_REMINDERS:
                _validate_stored_fixed(row)
            else:
                validate_custom(reminder_details(row))
        except (LifeValidationError, TypeError, ValueError) as exc:
            errors.append(f"{reminder_id}: {exc}")
    return errors


def validate_custom(record: dict[str, Any]) -> None:
    reminder_id = str(record.get("id", ""))
    if not ID_PATTERN.fullmatch(reminder_id):
        raise LifeValidationError("id must match ^[a-z][a-z0-9-]{1,63}$")
    if reminder_id in FIXED_REMINDERS:
        raise LifeValidationError(f"id conflicts with fixed reminder: {reminder_id}")
    if not str(record.get("title", "")).strip():
        raise LifeValidationError("title is required")
    if not str(record.get("action", "")).strip():
        raise LifeValidationError("action is required")
    kind = str(record.get("kind", ""))
    if kind not in CUSTOM_KINDS:
        raise LifeValidationError("kind must be one-off, weekly, or interval")
    _validate_time(str(record.get("time", "")))
    if kind == "one-off":
        _validate_date(str(record.get("date", "")))
    elif kind == "weekly":
        _validate_weekday(str(record.get("weekday", "")))
    else:
        _validate_date(str(record.get("base_date", "")))
        _validate_days(record.get("days"))


def _validate_fixed_update(reminder_id: str, values: dict[str, Any]) -> None:
    allowed = FIXED_REMINDERS[reminder_id].editable_fields
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise LifeValidationError(f"{reminder_id} does not support field(s): {', '.join(unknown)}")
    if "time" in values:
        _validate_time(str(values["time"]))
    if "base_date" in values:
        _validate_date(str(values["base_date"]))
    if "days" in values:
        _validate_days(values["days"])
    if "weekday" in values:
        _validate_weekday(str(values["weekday"]))
    for key in ("title", "action", "note", "confirmation_prompt"):
        if key in values and not str(values[key]).strip():
            raise LifeValidationError(f"{key} must not be empty")


def _validate_stored_fixed(row: ReminderRecord) -> None:
    schedule = _schedule(row)
    if "time" in schedule:
        _validate_time(str(schedule["time"]))
    if "base_date" in schedule:
        _validate_date(str(schedule["base_date"]))
    if "days" in schedule:
        _validate_days(schedule["days"])
    if "weekday" in schedule:
        _validate_weekday(str(schedule["weekday"]))
    if "weekdays" in schedule:
        weekdays = schedule["weekdays"]
        if not isinstance(weekdays, list) or not weekdays:
            raise LifeValidationError("weekdays must be a non-empty list")
        for weekday in weekdays:
            _validate_weekday(str(weekday))
    if "interval_months" in schedule:
        _validate_days(schedule["interval_months"])
    if schedule.get("weekend_policy", "previous_sunday") != "previous_sunday":
        raise LifeValidationError("unsupported haircut weekend_policy")
    for key in ("title", "action"):
        if not str(row[key]).strip():
            raise LifeValidationError(f"{key} must not be empty")


def _validate_time(value: str) -> None:
    if not TIME_PATTERN.fullmatch(value):
        raise LifeValidationError("time must be HH:MM")


def _validate_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise LifeValidationError("date must be YYYY-MM-DD") from exc


def _validate_weekday(value: str) -> None:
    if value not in WEEKDAYS:
        raise LifeValidationError("weekday must be one of mon,tue,wed,thu,fri,sat,sun")


def _validate_days(value: Any) -> None:
    if int(value or 0) < 1:
        raise LifeValidationError("days must be >= 1")


def _required(store: PersonalContextRepositoryPort, reminder_id: str) -> ReminderRecord:
    row = store.get_reminder_by_key(reminder_key=reminder_id)
    if row is None:
        raise LifeValidationError(f"unknown reminder: {reminder_id}")
    return row


def _schedule(row: ReminderRecord) -> dict[str, Any]:
    parsed = json.loads(str(row["schedule_json"] or "{}"))
    return parsed if isinstance(parsed, dict) else {}


def _save(store, row, **overrides) -> ReminderRecord:
    return store.upsert_reminder(
        routine_id=str(row["routine_id"] or ""),
        reminder_key=str(row["reminder_key"]),
        title=str(overrides.get("title", row["title"])),
        cadence=str(row["cadence"]),
        schedule=overrides.get("schedule", _schedule(row)),
        action=str(overrides.get("action", row["action"])),
        note=str(overrides.get("note", row["note"])),
        requires_confirmation=bool(row["requires_confirmation"]),
        enabled=bool(overrides.get("enabled", row["enabled"])),
    )
