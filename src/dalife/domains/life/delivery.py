from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from dalife.domains.life.dispatch import (
    LifeDispatch,
    mark_life_dispatch_sent,
    prepare_due_life_dispatches,
)
from dalife.ports import PersonalContextRepositoryPort


class LifeMessageClient(Protocol):
    def send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LifeDeliveryReport:
    due: int
    sent: int
    failed: int
    skipped: int
    event_ids: tuple[str, ...]
    errors: tuple[str, ...]


def deliver_due_life_reminders(
    store: PersonalContextRepositoryPort,
    client: LifeMessageClient,
    *,
    chat_id: str,
    now: datetime,
) -> LifeDeliveryReport:
    dispatches = prepare_due_life_dispatches(store, now)
    sent = 0
    failed = 0
    skipped = 0
    event_ids: list[str] = []
    errors: list[str] = []
    for dispatch in dispatches:
        event_id = str(dispatch.event["id"])
        claimed = store.claim_reminder_event(event_id=event_id)
        if claimed is None:
            skipped += 1
            continue
        try:
            response = client.send_message(
                chat_id,
                dispatch.message,
                reply_markup=dispatch.reply_markup,
            )
            message_id = _telegram_message_id(response)
            mark_life_dispatch_sent(
                store,
                claimed,
                telegram_message_id=message_id,
                sent_at=now.isoformat(),
            )
            sent += 1
            event_ids.append(event_id)
        except Exception as exc:
            payload = _payload(claimed)
            payload["last_delivery_error"] = str(exc)
            payload["last_delivery_failed_at"] = now.isoformat()
            store.update_reminder_event_response(
                event_id=event_id,
                status="failed",
                response_payload=payload,
            )
            failed += 1
            errors.append(str(exc))
    return LifeDeliveryReport(
        due=len(dispatches),
        sent=sent,
        failed=failed,
        skipped=skipped,
        event_ids=tuple(event_ids),
        errors=tuple(errors),
    )


def _telegram_message_id(response: dict[str, Any]) -> str:
    result = response.get("result")
    if not isinstance(result, dict) or result.get("message_id") is None:
        raise RuntimeError("Telegram send response did not include message_id")
    return str(result["message_id"])


def _payload(event: Any) -> dict[str, Any]:
    raw = event["response_payload_json"]
    parsed = json.loads(raw or "{}") if isinstance(raw, str) else raw
    return dict(parsed) if isinstance(parsed, dict) else {}
