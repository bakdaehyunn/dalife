from __future__ import annotations

import uuid
from typing import Any

from dalife.json_utils import dumps
from dalife.models import BotPromptRecord
from dalife.persistence.common import insert_bot_prompt_event, optional_record, records, utc_now
from dalife.persistence.database import RepositoryBase


class PromptRepository(RepositoryBase):
    def create_bot_prompt(
        self,
        *,
        prompt_key: str,
        chat_id: str,
        prompt_type: str,
        capture_id: str = "",
        archive_item_id: str = "",
        insight_note_id: str = "",
        title: str,
        body: str,
        recommended_action: str,
        choices: list[dict[str, str]],
    ) -> BotPromptRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO bot_prompts(
                  id, prompt_key, chat_id, prompt_type, status,
                  capture_id, archive_item_id, insight_note_id,
                  title, body, recommended_action, choices_json,
                  selected_payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                ON CONFLICT(prompt_key) DO UPDATE SET
                  title = excluded.title,
                  body = excluded.body,
                  recommended_action = excluded.recommended_action,
                  choices_json = excluded.choices_json,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    prompt_key,
                    chat_id,
                    prompt_type,
                    capture_id or None,
                    archive_item_id or None,
                    insight_note_id or None,
                    title,
                    body,
                    recommended_action,
                    dumps(choices),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM bot_prompts WHERE prompt_key = ?", (prompt_key,)).fetchone()
            if row is None:
                raise RuntimeError("failed to insert or load bot prompt")
            return BotPromptRecord.from_mapping(row)

    def get_bot_prompt(self, prompt_id: str) -> BotPromptRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(conn.execute("SELECT * FROM bot_prompts WHERE id = ?", (prompt_id,)).fetchone(), BotPromptRecord)

    def mark_bot_prompt_sent(self, prompt_id: str, *, telegram_message_id: str = "") -> None:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE bot_prompts
                SET status = CASE WHEN status = 'pending' THEN 'sent' ELSE status END,
                    telegram_message_id = COALESCE(NULLIF(?, ''), telegram_message_id),
                    sent_at = COALESCE(NULLIF(sent_at, ''), ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (telegram_message_id, now, now, prompt_id),
            )
            insert_bot_prompt_event(conn, prompt_id=prompt_id, event_type="sent", payload={"telegram_message_id": telegram_message_id})

    def record_bot_prompt_choice(
        self,
        prompt_id: str,
        *,
        choice: str,
        actor_user_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> BotPromptRecord | None:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM bot_prompts WHERE id = ?", (prompt_id,)).fetchone()
            if row is None:
                return None
            if str(row["selected_choice"] or "") == choice:
                return BotPromptRecord.from_mapping(row)
            conn.execute(
                """
                UPDATE bot_prompts
                SET status = 'responded',
                    selected_choice = ?,
                    selected_payload_json = ?,
                    responded_at = COALESCE(NULLIF(responded_at, ''), ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (choice, dumps(payload or {}), now, now, prompt_id),
            )
            insert_bot_prompt_event(
                conn,
                prompt_id=prompt_id,
                event_type="choice",
                choice=choice,
                actor_user_id=actor_user_id,
                payload=payload or {},
            )
            return optional_record(conn.execute("SELECT * FROM bot_prompts WHERE id = ?", (prompt_id,)).fetchone(), BotPromptRecord)

    def list_bot_prompts(self, *, status: str = "", limit: int = 20) -> list[BotPromptRecord]:
        self.init_db()
        where = ""
        params: list[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        params.append(limit)
        with self.connect() as conn:
            return records(
                conn.execute(
                    f"""
                    SELECT * FROM bot_prompts
                    {where}
                    ORDER BY created_at DESC, id ASC
                    LIMIT ?
                    """,
                    tuple(params),
                ),
                BotPromptRecord,
            )
