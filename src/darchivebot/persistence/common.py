from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

from darchivebot.json_utils import dumps
from darchivebot.models import Record
from darchivebot.time_utils import utc_now


MAX_PROCESSING_RETRY_ATTEMPTS = 5
RETRY_BACKOFF_MINUTES = (5, 15, 60, 360)
StoredRecordT = TypeVar("StoredRecordT", bound=Record)


def records(rows: Any, record_type: type[StoredRecordT]) -> list[StoredRecordT]:
    return [record_type.from_mapping(row) for row in rows]


def optional_record(row: Any, record_type: type[StoredRecordT]) -> StoredRecordT | None:
    return record_type.from_mapping(row) if row is not None else None


def retry_delay_for_attempt(attempt: int) -> timedelta:
    index = min(max(attempt - 1, 0), len(RETRY_BACKOFF_MINUTES) - 1)
    return timedelta(minutes=RETRY_BACKOFF_MINUTES[index])


def unix_to_iso(value: int | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")


def list_value(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def insert_bot_prompt_event(
    conn: sqlite3.Connection,
    *,
    prompt_id: str,
    event_type: str,
    choice: str = "",
    actor_user_id: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO bot_prompt_events(
          id, prompt_id, event_type, choice, actor_user_id, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            prompt_id,
            event_type,
            choice,
            actor_user_id,
            dumps(payload or {}),
            utc_now(),
        ),
    )
