from __future__ import annotations

import sqlite3
from typing import Any

from dalife.archive_values import (
    json_string_list as json_list,
    raw_payload_string_list as raw_json_list,
)
from dalife.json_utils import dumps


def archive_rows_for_search(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
              ai.*,
              c.text AS capture_text,
              c.caption AS capture_caption,
              COALESCE(GROUP_CONCAT(et.text, char(10)), '') AS extracted_text_sources
            FROM archive_items ai
            JOIN captures c ON c.id = ai.capture_id
            LEFT JOIN extracted_texts et ON et.capture_id = ai.capture_id
            GROUP BY ai.id
            ORDER BY ai.id ASC
            """
        )
    )


def archive_item_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM archive_items").fetchone()[0])


def archive_search_count(conn: sqlite3.Connection) -> int:
    try:
        return int(conn.execute("SELECT COUNT(*) FROM archive_search_fts").fetchone()[0])
    except sqlite3.OperationalError:
        return -1


def rebuild_search_index_conn(conn: sqlite3.Connection) -> None:
    ensure_search_table(conn)
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


def ensure_search_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS archive_search_fts USING fts5(
          archive_item_id UNINDEXED,
          capture_id UNINDEXED,
          title,
          summary,
          extracted_text,
          tags,
          interests,
          topics,
          questions,
          insight_seed,
          source_text,
          tokenize = 'unicode61'
        )
        """
    )


def search_index_values(row: sqlite3.Row) -> tuple[str, str, str, str, str, str, str, str, str, str, str]:
    tags = json_list(row["tags_json"])
    secondary_interests = json_list(row["secondary_interests_json"])
    questions = json_list(row["questions_json"])
    key_points = json_list(row["key_points_json"])
    relation_candidates = json_list(row["relation_candidates_json"])
    interests = [str(row["primary_interest"] or "").strip(), *secondary_interests]
    topics = [str(row["topic"] or "").strip(), str(row["subtopic"] or "").strip()]
    summary_parts = [
        row["summary"],
        row["core_summary"],
        row["why_saved"],
        row["classification_reason"],
        row["revisit_reason"],
        *key_points,
        *relation_candidates,
    ]
    source_parts = [row["capture_text"], row["capture_caption"], row["extracted_text_sources"]]
    return (
        str(row["id"]),
        str(row["capture_id"]),
        search_text(row["title"]),
        join_search_text(summary_parts),
        search_text(row["raw_extracted_text"] or row["extracted_text"]),
        join_search_text(tags),
        join_search_text(interests),
        join_search_text(topics),
        join_search_text(questions),
        search_text(row["insight_seed"]),
        join_search_text(source_parts),
    )


def join_search_text(values: list[Any]) -> str:
    return " ".join(search_text(value) for value in values if search_text(value))


def search_text(value: Any) -> str:
    return str(value or "").replace("\x00", " ").strip()


def migrate_db(conn: sqlite3.Connection) -> None:
    ensure_search_table(conn)
    archive_columns = {row["name"] for row in conn.execute("PRAGMA table_info(archive_items)")}
    archive_additions = {
        "core_summary": "TEXT",
        "key_points_json": "TEXT",
        "context": "TEXT",
        "raw_extracted_text": "TEXT",
        "why_saved": "TEXT",
        "primary_interest": "TEXT",
        "secondary_interests_json": "TEXT",
        "topic": "TEXT",
        "subtopic": "TEXT",
        "classification_reason": "TEXT",
        "revisit_priority": "TEXT",
        "revisit_reason": "TEXT",
        "insight_seed": "TEXT",
        "questions_json": "TEXT NOT NULL DEFAULT '[]'",
        "relation_candidates_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, column_type in archive_additions.items():
        if column not in archive_columns:
            try:
                conn.execute(f"ALTER TABLE archive_items ADD COLUMN {column} {column_type}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    capture_columns = {row["name"] for row in conn.execute("PRAGMA table_info(captures)")}
    capture_additions = {
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "next_retry_at": "TEXT",
        "last_error": "TEXT",
    }
    for column, column_type in capture_additions.items():
        if column not in capture_columns:
            try:
                conn.execute(f"ALTER TABLE captures ADD COLUMN {column} {column_type}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
    conn.execute("CREATE INDEX IF NOT EXISTS idx_captures_retry ON captures(status, next_retry_at, created_at)")
    evidence_columns = {row["name"] for row in conn.execute("PRAGMA table_info(evidence_items)")}
    if evidence_columns and "area_id" not in evidence_columns:
        try:
            conn.execute("ALTER TABLE evidence_items ADD COLUMN area_id TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    if evidence_columns:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evidence_items_area ON evidence_items(area_id, collected_at)"
        )
    query_ledger_columns = {row["name"] for row in conn.execute("PRAGMA table_info(query_ledger)")}
    if query_ledger_columns:
        conn.execute(
            """
            DELETE FROM query_ledger
            WHERE rowid NOT IN (
              SELECT MAX(rowid)
              FROM query_ledger
              GROUP BY domain, provider, query_text, facet, sort_mode, page
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_query_ledger_identity
            ON query_ledger(domain, provider, query_text, facet, sort_mode, page)
            """
        )
    backfill_archive_semantic_json(conn)
    if archive_search_count(conn) != archive_item_count(conn):
        rebuild_search_index_conn(conn)


def backfill_archive_semantic_json(conn: sqlite3.Connection) -> None:
    rows = list(conn.execute("SELECT id, raw_codex_json, questions_json, relation_candidates_json FROM archive_items"))
    for row in rows:
        questions = json_list(row["questions_json"])
        relation_candidates = json_list(row["relation_candidates_json"])
        updates: dict[str, str] = {}
        if not questions:
            raw_questions = raw_json_list(row["raw_codex_json"], "questions")
            if raw_questions:
                updates["questions_json"] = dumps(raw_questions)
        if not relation_candidates:
            raw_relations = raw_json_list(row["raw_codex_json"], "relation_candidates")
            if raw_relations:
                updates["relation_candidates_json"] = dumps(raw_relations)
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE archive_items SET {assignments} WHERE id = ?",
                (*updates.values(), row["id"]),
            )
