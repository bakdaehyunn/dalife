from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from darchivebot.json_utils import dumps
from darchivebot.models import CaptureFileRecord, CaptureRecord, CaptureSummaryRecord
from darchivebot.persistence.common import (
    MAX_PROCESSING_RETRY_ATTEMPTS,
    optional_record,
    records,
    retry_delay_for_attempt,
    unix_to_iso,
    utc_now,
)
from darchivebot.persistence.database import RepositoryBase


class CaptureRepository(RepositoryBase):
    def add_capture(
        self,
        *,
        capture_key: str,
        chat_id: str,
        message_id: int,
        chat_type: str,
        chat_title: str,
        sender_user_id: str,
        sender_name: str,
        message_date: int | None,
        text: str,
        caption: str,
        content_kind: str,
        raw_message: dict[str, Any],
    ) -> str:
        self.init_db()
        now = utc_now()
        message_datetime = unix_to_iso(message_date)
        capture_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO captures(
                  id, capture_key, chat_id, message_id, chat_type, chat_title,
                  sender_user_id, sender_name, message_date, message_datetime,
                  text, caption, content_kind, raw_message_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    capture_id,
                    capture_key,
                    chat_id,
                    message_id,
                    chat_type,
                    chat_title,
                    sender_user_id,
                    sender_name,
                    message_date,
                    message_datetime,
                    text,
                    caption,
                    content_kind,
                    dumps(raw_message),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT id FROM captures WHERE capture_key = ?", (capture_key,)).fetchone()
        if row is None:
            raise RuntimeError("failed to insert or load capture")
        return str(row["id"])

    def add_file(
        self,
        *,
        capture_id: str,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        file_kind: str,
        mime_type: str,
        file_name: str,
        file_size: int | None,
        local_path: str,
        download_status: str,
    ) -> str:
        self.init_db()
        file_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO capture_files(
                  id, capture_id, telegram_file_id, telegram_file_unique_id,
                  file_kind, mime_type, file_name, file_size, local_path,
                  download_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    capture_id,
                    telegram_file_id,
                    telegram_file_unique_id,
                    file_kind,
                    mime_type,
                    file_name,
                    file_size,
                    local_path,
                    download_status,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT id FROM capture_files
                WHERE capture_id = ? AND telegram_file_id = ?
                """,
                (capture_id, telegram_file_id),
            ).fetchone()
        if row is None:
            raise RuntimeError("failed to insert or load capture file")
        return str(row["id"])

    def pending_captures(self, limit: int) -> list[CaptureRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT * FROM captures
                    WHERE status = 'pending'
                       OR (
                         status = 'failed_retryable'
                         AND (next_retry_at IS NULL OR next_retry_at = '' OR next_retry_at <= ?)
                       )
                    ORDER BY created_at ASC
                    LIMIT ?
                    """,
                    (utc_now(), limit),
                ),
                CaptureRecord,
            )

    def files_for_capture(self, capture_id: str) -> list[CaptureFileRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    "SELECT * FROM capture_files WHERE capture_id = ? ORDER BY created_at ASC",
                    (capture_id,),
                ),
                CaptureFileRecord,
            )

    def list_captures(self, limit: int) -> list[CaptureRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    "SELECT * FROM captures ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ),
                CaptureRecord,
            )

    def list_capture_summaries(self, limit: int, interest: str = "") -> list[CaptureSummaryRecord]:
        self.init_db()
        interest = interest.strip().lower()
        where_clause = ""
        params: list[Any] = []
        if interest:
            where_clause = """
                    WHERE ai.id IS NOT NULL
                      AND (
                        LOWER(COALESCE(ai.primary_interest, '')) = ?
                        OR LOWER(COALESCE(ai.secondary_interests_json, '')) LIKE ?
                      )
                    """
            params.extend([interest, f"%{interest}%"])
        params.append(limit)
        with self.connect() as conn:
            return records(
                conn.execute(
                    f"""
                    SELECT
                      c.*,
                      COUNT(cf.id) AS file_count,
                      COALESCE(GROUP_CONCAT(DISTINCT cf.download_status), '') AS file_download_statuses,
                      CASE WHEN ai.id IS NULL THEN 0 ELSE 1 END AS has_archive_item,
                      COALESCE(ai.title, '') AS archive_title,
                      COALESCE(ai.core_summary, ai.summary, '') AS archive_core_summary,
                      COALESCE(ai.why_saved, '') AS archive_why_saved,
                      COALESCE(ai.primary_interest, '') AS archive_primary_interest,
                      COALESCE(ai.secondary_interests_json, '[]') AS archive_secondary_interests_json,
                      COALESCE(ai.topic, '') AS archive_topic,
                      COALESCE(ai.subtopic, '') AS archive_subtopic,
                      COALESCE(ai.needs_review, 0) AS archive_needs_review
                    FROM captures c
                    LEFT JOIN capture_files cf ON cf.capture_id = c.id
                    LEFT JOIN archive_items ai ON ai.capture_id = c.id
                    {where_clause}
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    LIMIT ?
                    """,
                    tuple(params),
                ),
                CaptureSummaryRecord,
            )

    def get_capture(self, capture_id: str) -> CaptureRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone(), CaptureRecord)

    def mark_capture_status(self, capture_id: str, status: str) -> None:
        self.init_db()
        with self.connect() as conn:
            conn.execute(
                "UPDATE captures SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), capture_id),
            )

    def mark_capture_processed(self, capture_id: str) -> None:
        self.init_db()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE captures
                SET status = 'processed', retry_count = 0, next_retry_at = '', last_error = '', updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), capture_id),
            )

    def mark_capture_failed(
        self,
        capture_id: str,
        *,
        error: str,
        max_attempts: int = MAX_PROCESSING_RETRY_ATTEMPTS,
    ) -> dict[str, Any]:
        self.init_db()
        now = datetime.now(timezone.utc)
        error_text = str(error)[:4000]
        with self.connect() as conn:
            row = conn.execute("SELECT retry_count FROM captures WHERE id = ?", (capture_id,)).fetchone()
            previous_count = int(row["retry_count"] or 0) if row is not None else 0
            retry_count = previous_count + 1
            blocked = retry_count >= max_attempts
            status = "failed_blocked" if blocked else "failed_retryable"
            next_retry_at = "" if blocked else (now + retry_delay_for_attempt(retry_count)).isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE captures
                SET status = ?, retry_count = ?, next_retry_at = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, retry_count, next_retry_at, error_text, now.isoformat(timespec="seconds"), capture_id),
            )
        return {
            "status": status,
            "retry_count": retry_count,
            "next_retry_at": next_retry_at,
            "blocked": blocked,
        }
