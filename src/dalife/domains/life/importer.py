from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dalife.domains.life.defaults import FIXED_REMINDER_ORDER, get_fixed_spec
from dalife.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class HonsanamSnapshot:
    root: Path
    config: dict[str, Any]
    management: dict[str, Any]
    sent_keys: tuple[str, ...]
    interactions: tuple[dict[str, Any], ...]
    confirmations: tuple[dict[str, Any], ...]
    telegram_update_offset: int | None = None
    message_pattern: dict[str, str] | None = None


@dataclass(frozen=True)
class HonsanamImportReport:
    routines: int
    reminders: int
    sent_events: int
    interaction_events: int
    confirmation_events: int
    telegram_update_offset: int | None
    dry_run: bool = False


def load_honsanam_snapshot(root: Path) -> HonsanamSnapshot:
    root = root.expanduser().resolve()
    config_path = root / "reminders.toml"
    config = _load_toml(config_path) if config_path.exists() else {}
    management = _load_json(root / ".local/config/reminders.json", {"fixed": {}, "custom": []})
    sent = _load_json(root / ".local/state/sent.json", {"sent": []})
    interactions = _load_json(root / ".local/state/interactions.json", {"items": {}})
    confirmations = _load_json(
        root / ".local/state/confirmations.json",
        {"telegram_update_offset": None, "items": {}},
    )
    pattern_paths = (
        root / ".local/config/message_patterns.json",
        root / ".local/config/message-pattern.json",
    )
    pattern_path = next((path for path in pattern_paths if path.exists()), None)
    pattern = _load_json(pattern_path, {}) if pattern_path is not None else None
    return HonsanamSnapshot(
        root=root,
        config=config,
        management=management,
        sent_keys=tuple(sorted(str(item) for item in _list_value(sent, "sent"))),
        interactions=tuple(_object_items(interactions, "items")),
        confirmations=tuple(_object_items(confirmations, "items")),
        telegram_update_offset=_optional_int(confirmations.get("telegram_update_offset")),
        message_pattern={str(key): str(value) for key, value in pattern.items()} if pattern else None,
    )


def import_honsanam_snapshot(
    store: PersonalContextRepositoryPort,
    snapshot: HonsanamSnapshot,
    *,
    dry_run: bool = False,
) -> HonsanamImportReport:
    definitions = _reminder_definitions(snapshot)
    if dry_run:
        return HonsanamImportReport(
            routines=len(definitions),
            reminders=len(definitions),
            sent_events=len(snapshot.sent_keys),
            interaction_events=len(snapshot.interactions),
            confirmation_events=len(snapshot.confirmations),
            telegram_update_offset=snapshot.telegram_update_offset,
            dry_run=True,
        )

    reminders = {}
    if snapshot.message_pattern:
        store.set_app_setting(setting_key="life.message_pattern", value=snapshot.message_pattern)
    for definition in definitions:
        routine = store.upsert_routine(
            routine_key=definition["key"],
            title=definition["title"],
            description=definition["note"],
            enabled=definition["enabled"],
            metadata={"source": "honsanam-reminder", "legacy_type": definition["type"]},
        )
        reminders[definition["key"]] = store.upsert_reminder(
            routine_id=routine["id"],
            reminder_key=definition["key"],
            title=definition["title"],
            cadence=definition["cadence"],
            schedule=definition["schedule"],
            action=definition["action"],
            note=definition["note"],
            requires_confirmation=definition["requires_confirmation"],
            enabled=definition["enabled"],
        )

    for sent_key in snapshot.sent_keys:
        legacy_reminder_id, separator, scheduled_at = sent_key.partition(":")
        if not separator or not scheduled_at:
            continue
        base_key = _base_reminder_key(legacy_reminder_id, reminders)
        reminder = reminders.get(base_key)
        if reminder is None:
            continue
        store.upsert_reminder_event(
            reminder_id=reminder["id"],
            event_key=_event_key(legacy_reminder_id, scheduled_at),
            due_at=scheduled_at,
            status="sent",
            response_payload={"source": "honsanam-reminder", "legacy_sent_key": sent_key},
            sent_at=scheduled_at,
        )

    for item in snapshot.interactions:
        legacy_reminder_id = str(item.get("reminder_id", ""))
        scheduled_at = str(item.get("scheduled_at", ""))
        base_key = _base_reminder_key(legacy_reminder_id, reminders)
        reminder = reminders.get(base_key)
        if reminder is None or not scheduled_at:
            continue
        response = item.get("selected_response")
        responded_at = str(item.get("responded_at") or "")
        store.upsert_reminder_event(
            reminder_id=reminder["id"],
            event_key=_event_key(legacy_reminder_id, scheduled_at),
            due_at=scheduled_at,
            status="responded" if response else "sent",
            response_payload={
                "source": "honsanam-reminder",
                "legacy_interaction_id": item.get("interaction_id"),
                "selected_response": response,
                "telegram_update_id": item.get("telegram_update_id"),
            },
            sent_at=scheduled_at,
            responded_at=responded_at,
        )

    newest_pending = _newest_pending_confirmations(snapshot.confirmations, reminders)
    for item in snapshot.confirmations:
        legacy_reminder_id = str(item.get("reminder_id", ""))
        scheduled_at = str(item.get("scheduled_at", ""))
        base_key = _base_reminder_key(legacy_reminder_id, reminders)
        reminder = reminders.get(base_key)
        if reminder is None or not scheduled_at:
            continue
        completed = item.get("status") == "completed"
        is_latest = newest_pending.get(base_key) is item
        event_status = "completed" if completed else ("pending_confirmation" if is_latest else "superseded")
        last_prompted_at = str(item.get("last_prompted_at") or scheduled_at)
        followup_days = int(item.get("followup_days") or 7)
        due_at = scheduled_at if completed else _followup_due_at(last_prompted_at, followup_days)
        store.upsert_reminder_event(
            reminder_id=reminder["id"],
            event_key=f"honsanam:confirmation:{item.get('confirmation_id') or legacy_reminder_id}",
            due_at=due_at,
            status=event_status,
            response_payload={
                "source": "honsanam-reminder",
                "legacy_confirmation_id": item.get("confirmation_id"),
                "reminder_id": legacy_reminder_id,
                "scheduled_at": scheduled_at,
                "title": item.get("title"),
                "prompt": item.get("prompt"),
                "message": item.get("message"),
                "last_prompted_at": last_prompted_at,
                "last_answer": item.get("last_answer"),
                "followup_days": followup_days,
                "telegram_update_offset": snapshot.telegram_update_offset,
                "superseded_by_newer_occurrence": event_status == "superseded",
            },
            sent_at=last_prompted_at,
            responded_at=str(item.get("last_answered_at") or ""),
        )

    return HonsanamImportReport(
        routines=len(definitions),
        reminders=len(definitions),
        sent_events=len(snapshot.sent_keys),
        interaction_events=len(snapshot.interactions),
        confirmation_events=len(snapshot.confirmations),
        telegram_update_offset=snapshot.telegram_update_offset,
    )


def _reminder_definitions(snapshot: HonsanamSnapshot) -> list[dict[str, Any]]:
    fixed_overrides = snapshot.management.get("fixed", {})
    if not isinstance(fixed_overrides, dict):
        fixed_overrides = {}
    definitions = []
    for reminder_id in FIXED_REMINDER_ORDER:
        spec = get_fixed_spec(reminder_id)
        section = snapshot.config.get(spec.config_section, {})
        section = dict(section) if isinstance(section, dict) else {}
        override = fixed_overrides.get(reminder_id, {})
        override = dict(override) if isinstance(override, dict) else {}
        schedule = _effective_fixed_schedule(spec, section, override)
        definitions.append(
            {
                "key": reminder_id,
                "type": "fixed",
                "title": str(schedule.pop("title", spec.title)),
                "cadence": spec.schedule_kind,
                "action": str(schedule.pop("action", spec.default_action)),
                "note": str(schedule.pop("note", spec.default_note)),
                "enabled": bool(schedule.pop("enabled", True)),
                "requires_confirmation": bool(
                    schedule.pop("requires_confirmation", spec.requires_confirmation)
                ),
                "schedule": schedule,
            }
        )
    custom = snapshot.management.get("custom", [])
    if isinstance(custom, list):
        for item in custom:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            values = dict(item)
            definitions.append(
                {
                    "key": str(values.pop("id")),
                    "type": "custom",
                    "title": str(values.pop("title", "")),
                    "cadence": str(values.pop("kind", "custom")),
                    "action": str(values.pop("action", "")),
                    "note": str(values.pop("note", "")),
                    "enabled": bool(values.pop("enabled", True)),
                    "requires_confirmation": False,
                    "schedule": values,
                }
            )
    return definitions


def _effective_fixed_schedule(spec, section: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    if spec.section_prefix:
        prefix = spec.section_prefix
        values = {
            "enabled": bool(section.get("enabled", True)) and bool(section.get(f"{prefix}_enabled", True)),
            "title": section.get(f"{prefix}_title", spec.title),
            "time": section.get("notify_time"),
            "base_date": section.get("base_date"),
            "days": section.get(f"{prefix}_days"),
            "action": section.get(f"{prefix}_action", spec.default_action),
            "note": section.get(f"{prefix}_note", spec.default_note),
        }
    else:
        values = {
            **section,
            "enabled": bool(section.get("enabled", True)),
            "title": section.get("title", spec.title),
            "time": section.get("notify_time"),
            "action": section.get("action", spec.default_action),
            "note": section.get("note", spec.default_note),
        }
    values.update(override)
    return {key: value for key, value in values.items() if value is not None and key != "notify_time"}


def _base_reminder_key(legacy_id: str, reminders: dict[str, Any]) -> str:
    if legacy_id in reminders:
        return legacy_id
    if legacy_id.startswith("haircut-booking-"):
        return "haircut"
    matching = [key for key in reminders if legacy_id.startswith(f"{key}-")]
    return max(matching, key=len) if matching else legacy_id


def _event_key(legacy_reminder_id: str, scheduled_at: str) -> str:
    return f"honsanam:{legacy_reminder_id}:{scheduled_at}"


def _newest_pending_confirmations(
    confirmations: tuple[dict[str, Any], ...],
    reminders: dict[str, ReminderRecord],
) -> dict[str, dict[str, Any]]:
    newest: dict[str, dict[str, Any]] = {}
    for item in confirmations:
        if item.get("status") == "completed":
            continue
        base_key = _base_reminder_key(str(item.get("reminder_id", "")), reminders)
        if base_key not in reminders:
            continue
        current = newest.get(base_key)
        if current is None or str(item.get("scheduled_at") or "") > str(current.get("scheduled_at") or ""):
            newest[base_key] = item
    return newest


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    return payload


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _list_value(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"expected list at {key}")
    return value


def _object_items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {key}")
    return [item for item in value.values() if isinstance(item, dict)]


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _followup_due_at(last_prompted_at: str, followup_days: int) -> str:
    return (datetime.fromisoformat(last_prompted_at) + timedelta(days=followup_days)).isoformat()
