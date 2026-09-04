from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from darchivebot.domains.life.defaults import (
    FIXED_REMINDER_ORDER,
    default_reminder_config,
    fixed_spec_for_scheduled_id,
    get_fixed_spec,
)
from darchivebot.domains.life.schedule import due_reminders
from darchivebot.domains.life.schedule import ScheduledReminder
from darchivebot.domains.life.patterns import load_message_pattern
from darchivebot.models import ReminderEventRecord
from darchivebot.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class LifeDispatch:
    event: ReminderEventRecord
    title: str
    message: str
    reply_markup: dict[str, Any]


@dataclass(frozen=True)
class LifeCallback:
    kind: str
    reference: str
    action: str


@dataclass(frozen=True)
class LifeCallbackResult:
    event: ReminderEventRecord
    action: str
    answer_text: str


def prepare_due_life_dispatches(
    store: PersonalContextRepositoryPort,
    now: datetime,
    *,
    config: dict[str, Any] | None = None,
) -> list[LifeDispatch]:
    dispatches: list[LifeDispatch] = []
    effective_config = config if config is not None else life_config_from_store(store)
    for scheduled in due_reminders(now, effective_config, pattern=load_message_pattern(store)):
        spec = fixed_spec_for_scheduled_id(scheduled.reminder_id)
        reminder_key = spec.reminder_id if spec is not None else scheduled.reminder_id
        reminder = store.get_reminder_by_key(reminder_key=reminder_key)
        if reminder is None or not bool(reminder["enabled"]):
            continue
        event_key = f"life:{scheduled.sent_key}"
        existing = store.get_reminder_event(event_key=event_key)
        if existing is not None and existing["status"] not in {"pending", "failed"}:
            continue
        payload = {
            "source": "darchivebot",
            "scheduled_reminder_id": scheduled.reminder_id,
            "title": scheduled.title,
            "message": scheduled.message,
            "requires_confirmation": bool(reminder["requires_confirmation"]),
            "followup_days": _followup_days(effective_config, spec),
            "actions": [choice for _, choice in _interaction_labels(spec)],
        }
        message = scheduled.message
        if bool(reminder["requires_confirmation"]):
            prompt = _confirmation_prompt(effective_config, spec)
            payload["prompt"] = prompt
            message = f"{message}\n\n{prompt}"
        event = store.create_reminder_event_if_absent(
            reminder_id=str(reminder["id"]),
            event_key=event_key,
            due_at=scheduled.scheduled_at.isoformat(),
            status="pending",
            response_payload=payload,
        )
        dispatches.append(
            LifeDispatch(
                event=event,
                title=scheduled.title,
                message=message,
                reply_markup=inline_keyboard_for_life_event(
                    str(event["id"]),
                    _interaction_labels(spec),
                ),
            )
        )
    dispatches.extend(_due_confirmation_followups(store, now))
    return dispatches


def preview_due_life_reminders(
    store: PersonalContextRepositoryPort,
    now: datetime,
    *,
    config: dict[str, Any] | None = None,
) -> list[ScheduledReminder]:
    effective_config = config if config is not None else life_config_from_store(store)
    reminders: list[ScheduledReminder] = []
    for scheduled in due_reminders(now, effective_config, pattern=load_message_pattern(store)):
        spec = fixed_spec_for_scheduled_id(scheduled.reminder_id)
        reminder_key = spec.reminder_id if spec is not None else scheduled.reminder_id
        reminder = store.get_reminder_by_key(reminder_key=reminder_key)
        if reminder is None or not bool(reminder["enabled"]):
            continue
        existing = store.get_reminder_event(event_key=f"life:{scheduled.sent_key}")
        if existing is None or existing["status"] in {"pending", "failed"}:
            reminders.append(scheduled)
    for dispatch in _due_confirmation_followups(store, now):
        reminders.append(
            ScheduledReminder(
                reminder_id=str(dispatch.event["event_key"]),
                scheduled_at=datetime.fromisoformat(str(dispatch.event["due_at"])),
                title=dispatch.title,
                message=dispatch.message,
            )
        )
    return sorted(reminders, key=lambda item: (item.scheduled_at, item.reminder_id))


def life_config_from_store(store: PersonalContextRepositoryPort) -> dict[str, Any]:
    config = default_reminder_config()
    for reminder_id in FIXED_REMINDER_ORDER:
        spec = get_fixed_spec(reminder_id)
        config[spec.config_section]["enabled"] = False
        if spec.section_prefix:
            config[spec.config_section][f"{spec.section_prefix}_enabled"] = False

    custom: list[dict[str, Any]] = []
    for reminder in store.list_reminders():
        key = str(reminder["reminder_key"])
        spec = get_fixed_spec(key) if key in FIXED_REMINDER_ORDER else None
        schedule = _json_object(reminder["schedule_json"])
        common = {
            "enabled": bool(reminder["enabled"]),
            "title": str(reminder["title"]),
            "action": str(reminder["action"]),
            "note": str(reminder["note"]),
            **schedule,
        }
        if spec is None:
            custom.append({"id": key, "kind": str(reminder["cadence"]), **common})
            continue
        section = config[spec.config_section]
        if spec.section_prefix:
            prefix = spec.section_prefix
            for field in ("enabled", "title", "action", "note", "days"):
                if field in common:
                    section[f"{prefix}_{field}"] = common[field]
            for field in ("base_date", "time"):
                if field in common:
                    section["notify_time" if field == "time" else field] = common[field]
        else:
            section.update(common)
            if "time" in section:
                section["notify_time"] = section.pop("time")
        if bool(reminder["requires_confirmation"]):
            section["requires_confirmation"] = True
    config["custom"] = custom
    return config


def inline_keyboard_for_life_event(
    event_id: str,
    labels: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": label,
                    "callback_data": f"life:{event_id}:{action}",
                }
                for label, action in labels
            ]
        ]
    }


def parse_life_callback_data(data: str) -> LifeCallback | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in {"life", "confirm", "interact"}:
        return None
    kind, reference, action = parts
    if not reference or not action:
        return None
    return LifeCallback(kind=kind, reference=reference, action=action)


def apply_life_callback(
    store: PersonalContextRepositoryPort,
    data: str,
    *,
    responded_at: str,
    callback_query_id: str = "",
    chat_id: str = "",
    user_id: str = "",
) -> LifeCallbackResult | None:
    callback = parse_life_callback_data(data)
    if callback is None:
        return None
    if callback.kind == "life":
        event = store.get_reminder_event(event_id=callback.reference)
    else:
        event = store.find_reminder_event_by_callback_reference(
            callback_kind=callback.kind,
            reference=callback.reference,
        )
    if event is None:
        return None

    payload = _payload(event)
    allowed = {str(action) for action in payload.get("actions", [])}
    if not allowed:
        allowed = {"yes", "no"} if callback.kind == "confirm" or payload.get("prompt") else {
            "done",
            "later",
            "checked",
        }
    if callback.action not in allowed:
        return None

    payload.update(
        {
            "selected_response": callback.action,
            "last_answer": callback.action,
            "callback_query_id": callback_query_id,
            "callback_chat_id": chat_id,
            "callback_user_id": user_id,
        }
    )
    status = _status_for_action(callback.action)
    next_due_at = None
    if callback.action == "no":
        followup_days = int(payload.get("followup_days") or 7)
        next_due_at = _next_followup_at(event, responded_at, followup_days)
        payload["next_followup_at"] = next_due_at
    updated = store.update_reminder_event_response(
        event_id=str(event["id"]),
        status=status,
        response_payload=payload,
        responded_at=responded_at,
        due_at=next_due_at,
    )
    if updated is None:
        return None
    return LifeCallbackResult(
        event=updated,
        action=callback.action,
        answer_text=_answer_text(callback.action),
    )


def mark_life_dispatch_sent(
    store: PersonalContextRepositoryPort,
    event: ReminderEventRecord,
    *,
    telegram_message_id: str,
    sent_at: str,
) -> ReminderEventRecord | None:
    return store.update_reminder_event_response(
        event_id=str(event["id"]),
        status="sent",
        response_payload=_payload(event),
        telegram_message_id=telegram_message_id,
        sent_at=sent_at,
    )


def _payload(event: ReminderEventRecord) -> dict[str, Any]:
    raw = event["response_payload_json"]
    if isinstance(raw, str):
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    return dict(raw) if isinstance(raw, dict) else {}


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    return dict(raw) if isinstance(raw, dict) else {}


def _interaction_labels(spec: Any) -> tuple[tuple[str, str], ...]:
    if spec is None:
        return (("했음", "done"), ("나중에", "later"))
    return spec.interaction_labels


def _confirmation_prompt(config: dict[str, Any], spec: Any) -> str:
    if spec is None:
        return "완료했나요?"
    section = config.get(spec.config_section, {})
    if not isinstance(section, dict):
        return spec.confirmation_prompt or "완료했나요?"
    return str(section.get("confirmation_prompt") or spec.confirmation_prompt or "완료했나요?")


def _followup_days(config: dict[str, Any], spec: Any) -> int | None:
    if spec is None:
        return None
    section = config.get(spec.config_section, {})
    if not isinstance(section, dict):
        return spec.followup_days
    raw = section.get("followup_days", spec.followup_days)
    return int(raw) if raw is not None else None


def _status_for_action(action: str) -> str:
    if action == "yes":
        return "completed"
    if action == "no":
        return "pending_confirmation"
    if action == "later":
        return "deferred"
    return "responded"


def _answer_text(action: str) -> str:
    return {
        "yes": "완료로 기록했어요.",
        "no": "아직으로 기록했어요.",
        "later": "나중에로 기록했어요.",
        "done": "완료로 기록했어요.",
        "checked": "확인으로 기록했어요.",
    }.get(action, "기록했어요.")


def _due_confirmation_followups(
    store: PersonalContextRepositoryPort,
    now: datetime,
) -> list[LifeDispatch]:
    dispatches: list[LifeDispatch] = []
    for event in store.list_due_reminder_events(
        due_at=now.isoformat(),
        status="pending_confirmation",
    ):
        payload = _payload(event)
        message = str(payload.get("message") or payload.get("title") or "확인이 필요합니다.")
        prompt = str(payload.get("prompt") or "완료했나요?")
        if prompt not in message:
            message = f"{message}\n\n{prompt}"
        dispatches.append(
            LifeDispatch(
                event=event,
                title=str(payload.get("title") or "확인 필요"),
                message=message,
                reply_markup=inline_keyboard_for_life_event(
                    str(event["id"]),
                    (("예약했음", "yes"), ("아직", "no")),
                ),
            )
        )
    return dispatches


def _next_followup_at(
    event: ReminderEventRecord,
    responded_at: str,
    followup_days: int,
) -> str:
    responded = datetime.fromisoformat(responded_at)
    due = datetime.fromisoformat(str(event["due_at"]))
    if responded.tzinfo is not None and due.tzinfo is not None:
        responded = responded.astimezone(due.tzinfo)
    return (responded + timedelta(days=followup_days)).isoformat()
