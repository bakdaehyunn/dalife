from __future__ import annotations

from typing import Any

from darchivebot.models import ArchiveItemRecord
from darchivebot.persistence.common import records
from darchivebot.persistence.database import RepositoryBase
from darchivebot.persistence.search_index import (
    archive_item_count,
    archive_rows_for_search,
    archive_search_count,
    rebuild_search_index_conn,
    search_index_values,
)


class SearchRepository(RepositoryBase):
    def rebuild_search_index(self) -> dict[str, Any]:
        self.init_db()
        with self.connect() as conn:
            rows = archive_rows_for_search(conn)
            conn.execute("DELETE FROM archive_search_fts")
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO archive_search_fts(
                      archive_item_id, capture_id, title, summary, extracted_text,
                      tags, interests, topics, questions, insight_seed, source_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    search_index_values(row),
                )
        return {"indexed_archive_items": len(rows)}

    def search_archive(self, query: str, *, limit: int = 20) -> list[ArchiveItemRecord]:
        self.init_db()
        cleaned_query = query.strip()
        if not cleaned_query:
            return []
        with self.connect() as conn:
            if archive_search_count(conn) != archive_item_count(conn):
                rebuild_search_index_conn(conn)
            return records(
                conn.execute(
                    """
                    SELECT
                      ai.*,
                      c.id AS capture_row_id,
                      c.capture_key,
                      c.message_id,
                      c.message_datetime,
                      c.status AS capture_status,
                      c.content_kind,
                      c.text AS capture_text,
                      c.caption AS capture_caption,
                      fts.title AS search_title,
                      fts.summary AS search_summary,
                      fts.extracted_text AS search_extracted_text,
                      fts.tags AS search_tags,
                      fts.interests AS search_interests,
                      fts.topics AS search_topics,
                      fts.questions AS search_questions,
                      fts.insight_seed AS search_insight_seed,
                      fts.source_text AS search_source_text,
                      bm25(archive_search_fts) AS search_rank,
                      snippet(archive_search_fts, -1, '[', ']', '...', 12) AS search_snippet
                    FROM archive_search_fts fts
                    JOIN archive_items ai ON ai.id = fts.archive_item_id
                    JOIN captures c ON c.id = ai.capture_id
                    WHERE archive_search_fts MATCH ?
                    ORDER BY search_rank ASC, ai.updated_at DESC, ai.id ASC
                    LIMIT ?
                    """,
                    (cleaned_query, limit),
                ),
                ArchiveItemRecord,
            )

    def review_archive_items(
        self,
        *,
        limit: int = 20,
        needs_review_only: bool = False,
        revisit_only: bool = False,
    ) -> list[ArchiveItemRecord]:
        self.init_db()
        where = ["ai.id IS NOT NULL"]
        params: list[Any] = []
        if needs_review_only:
            where.append("ai.needs_review = 1")
        if revisit_only:
            where.append(
                """
                (
                  LOWER(COALESCE(ai.revisit_priority, '')) IN ('urgent', 'high')
                  OR COALESCE(ai.revisit_reason, '') <> ''
                  OR COALESCE(ai.insight_seed, '') <> ''
                )
                """
            )
        params.append(limit)
        with self.connect() as conn:
            return records(
                conn.execute(
                    f"""
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
                    WHERE {' AND '.join(where)}
                    ORDER BY
                      ai.needs_review DESC,
                      CASE LOWER(COALESCE(ai.revisit_priority, ''))
                        WHEN 'urgent' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                      END ASC,
                      ai.updated_at DESC,
                      ai.id ASC
                    LIMIT ?
                    """,
                    tuple(params),
                ),
                ArchiveItemRecord,
            )
