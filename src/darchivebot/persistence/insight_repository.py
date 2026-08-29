from __future__ import annotations

import uuid
from typing import Any

from darchivebot.archive_values import json_array
from darchivebot.json_utils import dumps
from darchivebot.models import InsightEvidenceRecord, InsightNoteRecord
from darchivebot.persistence.common import list_value, optional_record, records, utc_now
from darchivebot.persistence.database import RepositoryBase


class InsightRepository(RepositoryBase):
    def create_insight_note(self, note: dict[str, Any]) -> str:
        self.init_db()
        note_id = str(note.get("id") or uuid.uuid4())
        now = utc_now()
        evidence_ids = list_value(note.get("notable_archive_item_ids"))
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO insight_notes(
                  id, period_type, period_start, period_end, title, summary,
                  recurring_themes_json, related_capture_groups_json,
                  notable_archive_item_ids_json, questions_json, suggested_reviews_json,
                  review_status, confidence, needs_review, generator, raw_codex_json,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    str(note.get("period_type") or "weekly"),
                    str(note.get("period_start") or ""),
                    str(note.get("period_end") or ""),
                    str(note.get("title") or "Untitled insight note"),
                    str(note.get("summary") or ""),
                    dumps(json_array(note.get("recurring_themes"))),
                    dumps(json_array(note.get("related_capture_groups"))),
                    dumps(evidence_ids),
                    dumps(json_array(note.get("questions"))),
                    dumps(json_array(note.get("suggested_reviews"))),
                    str(note.get("review_status") or "draft"),
                    float(note.get("confidence") or 0.0),
                    1 if bool(note.get("needs_review")) else 0,
                    str(note.get("generator") or "local"),
                    dumps(note.get("raw_codex_json") or note),
                    now,
                    now,
                ),
            )
            for index, archive_item_id in enumerate(evidence_ids, start=1):
                conn.execute(
                    """
                    INSERT INTO insight_note_items(
                      id, insight_note_id, archive_item_id, evidence_role, evidence_order, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), note_id, archive_item_id, "evidence", index, now),
                )
        return note_id

    def list_insight_notes(self, limit: int = 20) -> list[InsightNoteRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT n.*, COUNT(i.id) AS evidence_count
                    FROM insight_notes n
                    LEFT JOIN insight_note_items i ON i.insight_note_id = n.id
                    GROUP BY n.id
                    ORDER BY n.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ),
                InsightNoteRecord,
            )

    def get_insight_note(self, note_id: str) -> InsightNoteRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(conn.execute("SELECT * FROM insight_notes WHERE id = ?", (note_id,)).fetchone(), InsightNoteRecord)

    def insight_note_items(self, note_id: str) -> list[InsightEvidenceRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT
                      ini.*,
                      ai.capture_id,
                      ai.title,
                      COALESCE(ai.core_summary, ai.summary, '') AS core_summary,
                      COALESCE(ai.primary_interest, '') AS primary_interest,
                      COALESCE(ai.topic, '') AS topic,
                      c.content_kind,
                      c.status AS capture_status
                    FROM insight_note_items ini
                    JOIN archive_items ai ON ai.id = ini.archive_item_id
                    JOIN captures c ON c.id = ai.capture_id
                    WHERE ini.insight_note_id = ?
                    ORDER BY ini.evidence_order ASC
                    """,
                    (note_id,),
                ),
                InsightEvidenceRecord,
            )
