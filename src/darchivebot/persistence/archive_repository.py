from __future__ import annotations

import uuid
from typing import Any

from darchivebot.json_utils import dumps
from darchivebot.models import ArchiveItemRecord
from darchivebot.persistence.common import list_value, optional_record, records, utc_now
from darchivebot.persistence.database import RepositoryBase
from darchivebot.persistence.search_index import rebuild_search_index_conn


class ArchiveRepository(RepositoryBase):
    def get_archive_item(self, capture_id: str) -> ArchiveItemRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(
                conn.execute("SELECT * FROM archive_items WHERE capture_id = ?", (capture_id,)).fetchone(),
                ArchiveItemRecord,
            )

    def list_archive_items_for_graph(self, limit: int | None = None) -> list[ArchiveItemRecord]:
        self.init_db()
        sql = """
            SELECT
              ai.*,
              c.id AS capture_row_id,
              c.capture_key,
              c.message_id,
              c.message_datetime,
              c.status AS capture_status,
              c.content_kind,
              c.text AS capture_text,
              c.caption AS capture_caption
            FROM archive_items ai
            JOIN captures c ON c.id = ai.capture_id
            ORDER BY ai.updated_at DESC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        with self.connect() as conn:
            return records(conn.execute(sql, params), ArchiveItemRecord)

    def upsert_extracted_text(
        self,
        *,
        capture_id: str,
        source: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO extracted_texts(id, capture_id, source, text, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capture_id, source) DO UPDATE SET
                  text = excluded.text,
                  metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (str(uuid.uuid4()), capture_id, source, text, dumps(metadata or {}), now, now),
            )
            archive_row = conn.execute("SELECT id FROM archive_items WHERE capture_id = ?", (capture_id,)).fetchone()
            if archive_row is not None:
                rebuild_search_index_conn(conn)

    def upsert_archive_item(
        self,
        capture_id: str,
        item: dict[str, Any],
        *,
        source: str = "",
        schema_version: str = "",
        prompt_version: str = "",
    ) -> None:
        self.init_db()
        now = utc_now()
        title = str(item.get("title") or "").strip() or "Untitled capture"
        core_summary = str(item.get("core_summary") or item.get("summary") or "").strip()
        summary = core_summary
        key_points = list_value(item.get("key_points"))
        context = str(item.get("context") or "").strip()
        raw_extracted_text = str(item.get("raw_extracted_text") or item.get("extracted_text") or "").strip()
        extracted_text = raw_extracted_text
        why_saved = str(item.get("why_saved") or "").strip()
        source_language = str(item.get("source_language") or "unknown").strip() or "unknown"
        primary_interest = str(item.get("primary_interest") or "other/unknown").strip() or "other/unknown"
        secondary_interests = list_value(item.get("secondary_interests"))
        topic = str(item.get("topic") or "").strip()
        subtopic = str(item.get("subtopic") or "").strip()
        classification_reason = str(item.get("classification_reason") or "").strip()
        revisit_priority = str(item.get("revisit_priority") or "medium").strip().lower() or "medium"
        revisit_reason = str(item.get("revisit_reason") or "").strip()
        insight_seed = str(item.get("insight_seed") or "").strip()
        questions = list_value(item.get("questions"))
        relation_candidates = list_value(item.get("relation_candidates"))
        confidence = float(item.get("confidence") or 0.0)
        needs_review = 1 if bool(item.get("needs_review")) else 0
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO archive_items(
                  id, capture_id, title, summary, core_summary, key_points_json,
                  context, extracted_text, raw_extracted_text, why_saved, source_language,
                  tags_json, primary_interest, secondary_interests_json, topic, subtopic,
                  classification_reason, revisit_priority, revisit_reason, insight_seed,
                  questions_json, relation_candidates_json,
                  dates_mentioned_json, people_mentioned_json,
                  action_candidates_json, confidence, needs_review, raw_codex_json,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capture_id) DO UPDATE SET
                  title = excluded.title,
                  summary = excluded.summary,
                  core_summary = excluded.core_summary,
                  key_points_json = excluded.key_points_json,
                  context = excluded.context,
                  extracted_text = excluded.extracted_text,
                  raw_extracted_text = excluded.raw_extracted_text,
                  why_saved = excluded.why_saved,
                  source_language = excluded.source_language,
                  tags_json = excluded.tags_json,
                  primary_interest = excluded.primary_interest,
                  secondary_interests_json = excluded.secondary_interests_json,
                  topic = excluded.topic,
                  subtopic = excluded.subtopic,
                  classification_reason = excluded.classification_reason,
                  revisit_priority = excluded.revisit_priority,
                  revisit_reason = excluded.revisit_reason,
                  insight_seed = excluded.insight_seed,
                  questions_json = excluded.questions_json,
                  relation_candidates_json = excluded.relation_candidates_json,
                  dates_mentioned_json = excluded.dates_mentioned_json,
                  people_mentioned_json = excluded.people_mentioned_json,
                  action_candidates_json = excluded.action_candidates_json,
                  confidence = excluded.confidence,
                  needs_review = excluded.needs_review,
                  raw_codex_json = excluded.raw_codex_json,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    capture_id,
                    title,
                    summary,
                    core_summary,
                    dumps(key_points),
                    context,
                    extracted_text,
                    raw_extracted_text,
                    why_saved,
                    source_language,
                    dumps(list_value(item.get("tags"))),
                    primary_interest,
                    dumps(secondary_interests),
                    topic,
                    subtopic,
                    classification_reason,
                    revisit_priority,
                    revisit_reason,
                    insight_seed,
                    dumps(questions),
                    dumps(relation_candidates),
                    dumps(list_value(item.get("dates_mentioned"))),
                    dumps(list_value(item.get("people_mentioned"))),
                    dumps(list_value(item.get("action_candidates"))),
                    confidence,
                    needs_review,
                    dumps(item),
                    now,
                    now,
                ),
            )
            archive_row = conn.execute("SELECT id FROM archive_items WHERE capture_id = ?", (capture_id,)).fetchone()
            if archive_row is None:
                raise RuntimeError("failed to insert or load archive item")
            conn.execute(
                """
                INSERT INTO archive_interpretations(
                  id, capture_id, archive_item_id, source, schema_version, prompt_version,
                  title, core_summary, confidence, needs_review, raw_item_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    capture_id,
                    str(archive_row["id"]),
                    str(source or item.get("processor") or "unknown"),
                    str(schema_version or item.get("schema_version") or ""),
                    str(prompt_version or item.get("prompt_version") or ""),
                    title,
                    core_summary,
                    confidence,
                    needs_review,
                    dumps(item),
                    now,
                ),
            )
            rebuild_search_index_conn(conn)

    def archive_interpretations_for_capture(self, capture_id: str) -> list[ArchiveItemRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT * FROM archive_interpretations
                    WHERE capture_id = ?
                    ORDER BY created_at ASC, rowid ASC
                    """,
                    (capture_id,),
                ),
                ArchiveItemRecord,
            )
