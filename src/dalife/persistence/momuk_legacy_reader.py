from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def read_legacy_momuk_recommendations(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(recommendations)").fetchall()
        }
        required = {
            "id", "chat_id", "request_text", "area", "topic", "place_name",
            "category", "status_marker", "reason", "links_json", "search_keyword",
            "created_at",
        }
        if not required <= columns:
            missing = ", ".join(sorted(required - columns))
            raise ValueError(f"legacy Momuk recommendations schema is missing: {missing}")
        rows = conn.execute(
            """
            SELECT id, chat_id, request_text, area, topic, place_name, category,
                   status_marker, reason, links_json, search_keyword, created_at
            FROM recommendations
            ORDER BY created_at, id
            """
        ).fetchall()
    return [dict(row) for row in rows]
