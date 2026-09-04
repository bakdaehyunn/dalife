from __future__ import annotations

import json
import sqlite3

from darchivebot.domains.food import build_momuk_history_refresh_plan, import_momuk_history
from darchivebot.persistence.momuk_legacy_reader import read_legacy_momuk_recommendations
from darchivebot.storage import ArchiveStore


def legacy_rows() -> list[dict[str, object]]:
    base = {
        "chat_id": "chat-1",
        "request_text": "신정동 맛집",
        "area": "신정동",
        "topic": "맛집",
        "status_marker": "영업시간 미확인",
        "search_keyword": "신정동 맛집",
        "created_at": "2026-08-29T13:12:32",
    }
    return [
        base | {
            "id": "row-1",
            "place_name": "우이락 목동점",
            "category": "술집",
            "reason": "저녁 모임",
            "links_json": '[{"label":"블로그","url":"https://example.test/1"}]',
        },
        base | {
            "id": "row-2",
            "place_name": "다른 식당",
            "category": "한식",
            "reason": "한 끼",
            "links_json": "not-json",
        },
    ]


def test_momuk_history_import_is_dry_run_safe_and_idempotent(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.upsert_place(
        provider="kakao_local",
        provider_place_id="1",
        name="우이락 목동점",
        normalized_name="우이락목동점",
    )

    preview = import_momuk_history(store, legacy_rows(), dry_run=True)
    assert preview.imported_rows == 2
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM recommendation_sessions").fetchone()[0] == 0

    first = import_momuk_history(store, legacy_rows(), dry_run=False)
    second = import_momuk_history(store, legacy_rows(), dry_run=False)
    assert (first.sessions, first.candidates, first.linked_places) == (1, 2, 1)
    assert (second.imported_rows, second.sessions, second.candidates) == (0, 0, 0)
    with store.connect() as conn:
        session = conn.execute("SELECT * FROM recommendation_sessions").fetchone()
        candidates = conn.execute("SELECT * FROM recommendation_candidates ORDER BY rank").fetchall()
    assert json.loads(session["context_json"])["source"] == "momukbot"
    assert candidates[0]["place_id"] is not None
    assert json.loads(candidates[1]["score_breakdown_json"])["links"] == []


def test_legacy_reader_validates_and_reads_expected_columns(tmp_path):
    path = tmp_path / "momukbot.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE recommendations(
              id TEXT, chat_id TEXT, request_text TEXT, area TEXT, topic TEXT,
              place_name TEXT, category TEXT, status_marker TEXT, reason TEXT,
              links_json TEXT, search_keyword TEXT, raw_response TEXT, created_at TEXT
            )
            """
        )
        row = legacy_rows()[0]
        conn.execute(
            """
            INSERT INTO recommendations(
              id, chat_id, request_text, area, topic, place_name, category,
              status_marker, reason, links_json, search_keyword, created_at
            ) VALUES (:id, :chat_id, :request_text, :area, :topic, :place_name,
                      :category, :status_marker, :reason, :links_json,
                      :search_keyword, :created_at)
            """,
            row,
        )
    assert read_legacy_momuk_recommendations(path)[0]["id"] == "row-1"


def test_history_refresh_plan_is_area_scoped_and_prioritizes_repeat_candidates(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    rows = legacy_rows() + [
        legacy_rows()[1] | {
            "id": "row-3",
            "created_at": "2026-08-30T13:12:32",
        },
        legacy_rows()[1] | {
            "id": "row-4",
            "area": "이태원",
            "place_name": "이태원 식당",
            "created_at": "2026-08-31T13:12:32",
        },
    ]
    import_momuk_history(store, rows, dry_run=False)

    plan = build_momuk_history_refresh_plan(
        store,
        area="신정동",
        legacy_areas=("신정동",),
        place_limit=1,
    )

    assert [query.query_text for query in plan.queries] == [
        "신정동 다른 식당",
        '"다른 식당" 신정동 후기',
    ]
