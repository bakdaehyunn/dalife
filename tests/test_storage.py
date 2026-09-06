from __future__ import annotations

import sqlite3

from dalife.storage import ArchiveStore


def test_add_capture_is_idempotent(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    first = store.add_capture(
        capture_key="chat:1",
        chat_id="chat",
        message_id=1,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=1_700_000_000,
        text="hello",
        caption="",
        content_kind="text",
        raw_message={"message_id": 1},
    )
    second = store.add_capture(
        capture_key="chat:1",
        chat_id="chat",
        message_id=1,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=1_700_000_000,
        text="hello again",
        caption="",
        content_kind="text",
        raw_message={"message_id": 1},
    )

    assert first == second
    rows = store.list_captures(10)
    assert len(rows) == 1
    assert rows[0]["text"] == "hello"


def test_personal_context_tables_are_initialized(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.init_db()

    expected_tables = {
        "areas",
        "places",
        "evidence_items",
        "place_evidence",
        "tags",
        "place_tags",
        "query_ledger",
        "query_ledger_runs",
        "routines",
        "reminders",
        "reminder_events",
        "app_settings",
        "recommendation_sessions",
        "recommendation_candidates",
        "user_feedback",
        "course_plans",
        "course_plan_stops",
    }
    with store.connect() as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name IN ({})
            """.format(",".join("?" for _ in expected_tables)),
            sorted(expected_tables),
        ).fetchall()

    assert {row["name"] for row in rows} == expected_tables


def test_personal_context_food_foreign_keys_cascade(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="20551759",
        name="미성참숯정육식당",
        normalized_name="미성참숯정육식당",
        area_id=area["id"],
    )
    evidence = store.upsert_evidence_item(
        provider="naver_blog",
        url="https://blog.example/1",
        title="후기",
        snippet="맛집 후기",
    )
    match = store.link_place_evidence(
        place_id=place["id"],
        evidence_item_id=evidence["id"],
        match_type="exact_name",
        score=0.9,
        decision="matched",
        matched_terms=["미성참숯정육식당"],
    )

    assert match["score"] == 0.9

    with store.connect() as conn:
        conn.execute("DELETE FROM places WHERE id = ?", (place["id"],))
        remaining = conn.execute("SELECT COUNT(*) FROM place_evidence").fetchone()[0]

    assert remaining == 0


def test_personal_context_repository_upserts_area_place_and_evidence(tmp_path):
    store = ArchiveStore(tmp_path / "state")

    first_area = store.upsert_area(name="Itaewon", normalized_name="itaewon", radius_meters=1200)
    second_area = store.upsert_area(name="Itaewon-dong", normalized_name="itaewon", radius_meters=1500)
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-123",
        name="Dinner Place",
        normalized_name="dinnerplace",
        area_id=second_area["id"],
        map_url="https://place.map.kakao.com/place-123",
    )
    evidence = store.upsert_evidence_item(
        provider="naver_blog",
        url="https://blog.example/place-123",
        title="Dinner Place review",
        snippet="A useful dinner review",
        query_text="Itaewon dinner",
    )
    link = store.link_place_evidence(
        place_id=place["id"],
        evidence_item_id=evidence["id"],
        match_type="exact_name",
        score=0.87,
        decision="matched",
    )

    assert first_area["id"] == second_area["id"]
    assert second_area["name"] == "Itaewon-dong"
    assert second_area["radius_meters"] == 1500
    assert place["area_id"] == second_area["id"]
    assert evidence["query_text"] == "Itaewon dinner"
    assert link["decision"] == "matched"


def test_personal_context_repository_tracks_query_ledger(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="Itaewon", normalized_name="itaewon")

    first = store.upsert_query_ledger_entry(
        domain="food",
        provider="naver_blog",
        query_text="Itaewon dinner review",
        area_id=area["id"],
        facet="occasion",
        sort_mode="sim",
        quota_cost=1,
        next_run_at="2026-08-29T00:00:00+00:00",
    )
    second = store.upsert_query_ledger_entry(
        domain="food",
        provider="naver_blog",
        query_text="Itaewon dinner review",
        area_id=area["id"],
        facet="occasion",
        sort_mode="sim",
        quota_cost=2,
        next_run_at="2026-08-30T00:00:00+00:00",
    )
    due_before = store.list_due_query_ledger_entries(domain="food", due_at="2026-08-29T12:00:00+00:00")
    due_after = store.list_due_query_ledger_entries(domain="food", due_at="2026-08-30T12:00:00+00:00")
    updated = store.record_query_ledger_result(
        ledger_id=first["id"],
        yielded_count=7,
        failure_reason="",
        next_run_at="2026-09-01T00:00:00+00:00",
    )

    assert first["id"] == second["id"]
    assert second["quota_cost"] == 2
    assert due_before == []
    assert [row["id"] for row in due_after] == [first["id"]]
    assert updated is not None
    assert updated["yielded_count"] == 7
    assert updated["last_run_at"]
    assert updated["next_run_at"] == "2026-09-01T00:00:00+00:00"

    store.record_query_ledger_result(
        ledger_id=first["id"],
        yielded_count=3,
        next_run_at="2026-09-02T00:00:00+00:00",
    )
    assert store.query_ledger_cost_since(provider="naver_blog", since="0001-01-01T00:00:00+00:00") == 4
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) FROM query_ledger_runs").fetchone()[0] == 2


def test_personal_context_course_stops_can_reference_archive_food_and_life(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:course",
        chat_id="chat",
        message_id=101,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="이태원 코스 메모",
        caption="",
        content_kind="text",
        raw_message={"message_id": 101},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "Itaewon idea",
            "core_summary": "Try a quiet dinner course",
            "raw_extracted_text": "이태원 조용한 저녁 코스",
            "source_language": "ko",
            "primary_interest": "food",
            "topic": "course",
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    with store.connect() as conn:
        archive_item_id = conn.execute(
            "SELECT id FROM archive_items WHERE capture_id = ?",
            (capture_id,),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO places(
              id, provider, provider_place_id, name, normalized_name,
              first_seen_at, last_seen_at
            )
            VALUES('place-1', 'kakao', '123', 'Dinner Place', 'dinnerplace', 'now', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO routines(id, routine_key, title, created_at, updated_at)
            VALUES('routine-1', 'cleaning', 'Cleaning', 'now', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO reminders(id, routine_id, reminder_key, title, cadence, action, created_at, updated_at)
            VALUES('reminder-1', 'routine-1', 'weekend-cleaning', 'Weekend cleaning', 'weekly', 'clean', 'now', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO reminder_events(id, reminder_id, event_key, due_at, status, created_at, updated_at)
            VALUES('event-1', 'reminder-1', 'weekend-cleaning-1', 'now', 'pending', 'now', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO course_plans(id, title, status, generated_at)
            VALUES('course-1', 'Weekend plan', 'draft', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO course_plan_stops(
              id, course_plan_id, stop_order, source_domain, title, place_id,
              reminder_event_id, archive_item_id
            )
            VALUES('stop-1', 'course-1', 1, 'course', 'Dinner plus task', 'place-1', 'event-1', ?)
            """,
            (archive_item_id,),
        )
        row = conn.execute("SELECT * FROM course_plan_stops WHERE id = 'stop-1'").fetchone()

    assert row["place_id"] == "place-1"
    assert row["reminder_event_id"] == "event-1"
    assert row["archive_item_id"] == archive_item_id


def test_personal_context_repository_tracks_life_routines_and_due_events(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    routine = store.upsert_routine(
        routine_key="haircut",
        title="미용실 예약",
        description="monthly haircut booking",
        metadata={"source": "honsanam"},
    )
    routine_again = store.upsert_routine(
        routine_key="haircut",
        title="미용실 예약",
        description="updated",
    )
    reminder = store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="haircut",
        title="미용실 예약",
        cadence="monthly",
        schedule={"notify_time": "08:45"},
        action="오늘 미용실 예약하기",
        requires_confirmation=True,
    )
    event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="haircut-booking-2026-09-07",
        due_at="2026-09-07T08:45:00+09:00",
        status="pending",
    )
    due_before = store.list_due_reminder_events(due_at="2026-09-07T08:44:00+09:00")
    due_after = store.list_due_reminder_events(due_at="2026-09-07T08:45:00+09:00")
    updated_event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="haircut-booking-2026-09-07",
        due_at="2026-09-07T08:45:00+09:00",
        status="sent",
        telegram_message_id="123",
        sent_at="2026-09-07T08:45:05+09:00",
    )

    assert routine_again["id"] == routine["id"]
    assert routine_again["description"] == "updated"
    assert reminder["routine_id"] == routine["id"]
    assert reminder["requires_confirmation"] == 1
    assert event["event_key"] == "haircut-booking-2026-09-07"
    assert due_before == []
    assert [row["id"] for row in due_after] == [event["id"]]
    assert updated_event["id"] == event["id"]
    assert updated_event["status"] == "sent"
    assert updated_event["telegram_message_id"] == "123"


def test_personal_context_repository_records_user_feedback(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-1",
        name="Dinner Place",
        normalized_name="dinnerplace",
    )
    row = store.record_user_feedback(
        feedback_key="food:place-1:liked",
        domain="food",
        action="liked",
        place_id=place["id"],
        payload={"reason": "personal favorite"},
    )
    rows = store.list_user_feedback(domain="food", action="liked")

    assert row["domain"] == "food"
    assert row["action"] == "liked"
    assert row["place_id"] == place["id"]
    assert len(rows) == 1
    assert rows[0]["feedback_key"] == "food:place-1:liked"


def test_personal_context_repository_records_recommendation_session_candidates(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao",
        provider_place_id="place-1",
        name="Dinner Place",
        normalized_name="dinnerplace",
        area_id=area["id"],
    )
    session = store.create_recommendation_session(
        domain="food",
        request_text="신정동 저녁 추천",
        area_id=area["id"],
        context={"topic": "저녁"},
    )
    candidate = store.add_recommendation_candidate(
        session_id=session["id"],
        place_id=place["id"],
        rank=1,
        score=0.91,
        score_breakdown={"evidence": 0.9},
        evidence_tier="verified",
        explanation="good evidence",
    )
    candidates = store.list_recommendation_candidates(session_id=session["id"])

    assert session["domain"] == "food"
    assert session["status"] == "completed"
    assert candidate["place_id"] == place["id"]
    assert candidate["score"] == 0.91
    assert [row["id"] for row in candidates] == [candidate["id"]]


def test_archive_item_upsert_and_status(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:2",
        chat_id="chat",
        message_id=2,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="오늘 읽을 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 2},
    )

    store.upsert_extracted_text(capture_id=capture_id, source="codex", text="오늘 읽을 글")
    store.upsert_archive_item(
        capture_id,
        {
            "title": "읽을 글",
            "core_summary": "관심 글",
            "key_points": ["나중에 읽기"],
            "context": "text message",
            "raw_extracted_text": "오늘 읽을 글",
            "why_saved": "관심 있는 글",
            "source_language": "ko",
            "tags": ["reading"],
            "primary_interest": "career",
            "secondary_interests": ["AI"],
            "topic": "reading habit",
            "subtopic": "knowledge work",
            "classification_reason": "글 읽기와 업무 성장에 관한 내용",
            "revisit_priority": "high",
            "revisit_reason": "나중에 실행 계획으로 바꿀 수 있음",
            "insight_seed": "읽기 습관과 커리어 성장 연결",
            "questions": ["어떻게 꾸준히 읽을까?"],
            "relation_candidates": ["reading system"],
            "dates_mentioned": [],
            "people_mentioned": [],
            "action_candidates": [],
            "confidence": 0.9,
            "needs_review": False,
        },
    )
    store.mark_capture_status(capture_id, "processed")

    row = store.get_capture(capture_id)
    assert row is not None
    assert row["status"] == "processed"
    with store.connect() as conn:
        archive_count = conn.execute("SELECT COUNT(*) FROM archive_items").fetchone()[0]
        text_count = conn.execute("SELECT COUNT(*) FROM extracted_texts").fetchone()[0]
        archive = conn.execute("SELECT * FROM archive_items WHERE capture_id = ?", (capture_id,)).fetchone()
    assert archive_count == 1
    assert text_count == 1
    assert archive["summary"] == "관심 글"
    assert archive["core_summary"] == "관심 글"
    assert archive["extracted_text"] == "오늘 읽을 글"
    assert archive["raw_extracted_text"] == "오늘 읽을 글"
    assert "나중에 읽기" in archive["key_points_json"]
    assert archive["primary_interest"] == "career"
    assert "AI" in archive["secondary_interests_json"]
    assert archive["topic"] == "reading habit"
    assert archive["revisit_priority"] == "high"
    assert archive["insight_seed"] == "읽기 습관과 커리어 성장 연결"
    assert "어떻게 꾸준히 읽을까?" in archive["questions_json"]
    assert "reading system" in archive["relation_candidates_json"]
    interpretations = store.archive_interpretations_for_capture(capture_id)
    assert len(interpretations) == 1
    assert interpretations[0]["title"] == "읽을 글"
    assert interpretations[0]["source"] == "unknown"


def test_search_index_rebuild_is_deterministic_and_searchable(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:search",
        chat_id="chat",
        message_id=22,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="semantic archive capture",
        caption="",
        content_kind="text",
        raw_message={"message_id": 22},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "Semantic archive design",
            "core_summary": "FTS search should find reusable archive notes",
            "key_points": ["local retrieval matters"],
            "raw_extracted_text": "A local-first archive needs full text retrieval.",
            "source_language": "en",
            "tags": ["search", "archive"],
            "primary_interest": "AI",
            "secondary_interests": ["product"],
            "topic": "retrieval",
            "questions": ["How do I find this later?"],
            "insight_seed": "Search layer before viewpoint layer",
            "confidence": 0.9,
            "needs_review": False,
        },
    )

    first = store.rebuild_search_index()
    second = store.rebuild_search_index()
    rows = store.search_archive('"retrieval"', limit=10)

    assert first == second == {"indexed_archive_items": 1}
    assert len(rows) == 1
    assert rows[0]["capture_id"] == capture_id
    assert "retrieval" in rows[0]["search_topics"]


def test_search_index_refreshes_when_extracted_text_changes_after_archive_item(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:search-refresh",
        chat_id="chat",
        message_id=25,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="initial",
        caption="",
        content_kind="text",
        raw_message={"message_id": 25},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "Archive item",
            "core_summary": "Search refresh",
            "raw_extracted_text": "initial text",
            "source_language": "en",
            "primary_interest": "AI",
            "topic": "search",
            "confidence": 0.9,
            "needs_review": False,
        },
    )

    assert store.search_archive('"latekeyword"', limit=10) == []

    store.upsert_extracted_text(capture_id=capture_id, source="ocr", text="latekeyword from updated OCR")

    rows = store.search_archive('"latekeyword"', limit=10)
    assert len(rows) == 1
    assert rows[0]["capture_id"] == capture_id
    assert "latekeyword" in rows[0]["search_source_text"]


def test_review_archive_items_filters_needs_review_and_revisit(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    review_id = store.add_capture(
        capture_key="chat:review",
        chat_id="chat",
        message_id=23,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="needs review",
        caption="",
        content_kind="text",
        raw_message={"message_id": 23},
    )
    revisit_id = store.add_capture(
        capture_key="chat:revisit",
        chat_id="chat",
        message_id=24,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="revisit",
        caption="",
        content_kind="text",
        raw_message={"message_id": 24},
    )
    store.upsert_archive_item(
        review_id,
        {
            "title": "Weak capture",
            "core_summary": "Needs human review",
            "raw_extracted_text": "Needs human review",
            "source_language": "en",
            "primary_interest": "other/unknown",
            "topic": "",
            "confidence": 0.2,
            "needs_review": True,
        },
    )
    store.upsert_archive_item(
        revisit_id,
        {
            "title": "Useful project seed",
            "core_summary": "Return to this later",
            "raw_extracted_text": "Return to this later",
            "source_language": "en",
            "primary_interest": "product",
            "topic": "archive",
            "revisit_priority": "high",
            "revisit_reason": "convert into product task",
            "insight_seed": "local search workflow",
            "confidence": 0.8,
            "needs_review": False,
        },
    )

    needs_review = store.review_archive_items(needs_review_only=True)
    revisit = store.review_archive_items(revisit_only=True)

    assert [row["capture_id"] for row in needs_review] == [review_id]
    assert [row["capture_id"] for row in revisit] == [revisit_id]


def test_init_db_adds_structured_archive_columns_to_existing_db(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            """
            CREATE TABLE archive_items (
              id TEXT PRIMARY KEY,
              capture_id TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL,
              summary TEXT NOT NULL,
              extracted_text TEXT NOT NULL,
              source_language TEXT NOT NULL,
              tags_json TEXT NOT NULL,
              dates_mentioned_json TEXT NOT NULL,
              people_mentioned_json TEXT NOT NULL,
              action_candidates_json TEXT NOT NULL,
              confidence REAL NOT NULL,
              needs_review INTEGER NOT NULL,
              raw_codex_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

    store.init_db()

    with store.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(archive_items)")}
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {
        "core_summary",
        "key_points_json",
        "context",
        "raw_extracted_text",
        "why_saved",
        "primary_interest",
        "secondary_interests_json",
        "topic",
        "subtopic",
        "classification_reason",
        "revisit_priority",
        "revisit_reason",
        "insight_seed",
        "questions_json",
        "relation_candidates_json",
    } <= columns
    assert {"archive_interpretations", "insight_notes", "insight_note_items"} <= tables


def test_init_db_adds_retry_columns_to_existing_captures_table_before_index(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            """
            CREATE TABLE captures (
              id TEXT PRIMARY KEY,
              capture_key TEXT NOT NULL UNIQUE,
              chat_id TEXT NOT NULL,
              message_id INTEGER NOT NULL,
              chat_type TEXT,
              chat_title TEXT,
              sender_user_id TEXT,
              sender_name TEXT,
              message_date INTEGER,
              message_datetime TEXT,
              text TEXT,
              caption TEXT,
              content_kind TEXT NOT NULL,
              raw_message_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )

    store.init_db()

    with store.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(captures)")}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(captures)")}
    assert {"retry_count", "next_retry_at", "last_error"} <= columns
    assert "idx_captures_retry" in indexes


def test_init_db_adds_area_to_existing_evidence_table_before_area_index(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            """
            CREATE TABLE evidence_items (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              external_id TEXT,
              url TEXT NOT NULL,
              title TEXT NOT NULL,
              snippet TEXT NOT NULL,
              author TEXT,
              published_at TEXT,
              collected_at TEXT NOT NULL,
              query_text TEXT,
              raw_json TEXT NOT NULL DEFAULT '{}',
              UNIQUE(provider, url)
            )
            """
        )

    store.init_db()

    with store.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(evidence_items)")}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(evidence_items)")}
    assert "area_id" in columns
    assert "idx_evidence_items_area" in indexes


def test_init_db_adds_query_ledger_identity_index_and_deduplicates_old_rows(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    store.path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            """
            CREATE TABLE query_ledger (
              id TEXT PRIMARY KEY,
              domain TEXT NOT NULL,
              provider TEXT NOT NULL,
              query_text TEXT NOT NULL,
              area_id TEXT,
              facet TEXT NOT NULL DEFAULT '',
              sort_mode TEXT NOT NULL DEFAULT '',
              page INTEGER NOT NULL DEFAULT 1,
              quota_cost INTEGER NOT NULL DEFAULT 1,
              yielded_count INTEGER NOT NULL DEFAULT 0,
              failure_reason TEXT NOT NULL DEFAULT '',
              last_run_at TEXT,
              next_run_at TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        for row_id in ("old-1", "old-2"):
            conn.execute(
                """
                INSERT INTO query_ledger(
                  id, domain, provider, query_text, facet, sort_mode, page, created_at, updated_at
                ) VALUES (?, 'food', 'kakao_local', '신정동 맛집', 'broad_discovery', 'accuracy', 1, 'now', 'now')
                """,
                (row_id,),
            )

    store.init_db()
    first = store.upsert_query_ledger_entry(
        domain="food",
        provider="kakao_local",
        query_text="신정동 맛집",
        facet="broad_discovery",
        sort_mode="accuracy",
        page=1,
        quota_cost=2,
    )
    second = store.upsert_query_ledger_entry(
        domain="food",
        provider="kakao_local",
        query_text="신정동 맛집",
        facet="broad_discovery",
        sort_mode="accuracy",
        page=1,
        quota_cost=3,
    )

    with store.connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM query_ledger").fetchone()[0]
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(query_ledger)")}
    assert count == 1
    assert first["id"] == second["id"]
    assert second["quota_cost"] == 3
    assert "uq_query_ledger_identity" in indexes


def test_pending_captures_respect_retry_backoff_and_blocked_status(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:retry",
        chat_id="chat",
        message_id=100,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="retry me",
        caption="",
        content_kind="text",
        raw_message={"message_id": 100},
    )

    first_failure = store.mark_capture_failed(capture_id, error="temporary codex failure", max_attempts=3)

    assert first_failure["status"] == "failed_retryable"
    assert first_failure["retry_count"] == 1
    assert first_failure["next_retry_at"]
    assert store.pending_captures(10) == []

    with store.connect() as conn:
        conn.execute("UPDATE captures SET next_retry_at = '2000-01-01T00:00:00+00:00' WHERE id = ?", (capture_id,))
    assert [row["id"] for row in store.pending_captures(10)] == [capture_id]

    store.mark_capture_failed(capture_id, error="temporary codex failure", max_attempts=3)
    blocked = store.mark_capture_failed(capture_id, error="still failing", max_attempts=3)

    row = store.get_capture(capture_id)
    assert row is not None
    assert blocked["status"] == "failed_blocked"
    assert row["status"] == "failed_blocked"
    assert row["retry_count"] == 3
    assert row["last_error"] == "still failing"
    assert store.pending_captures(10) == []


def test_mark_capture_processed_resets_retry_state(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = store.add_capture(
        capture_key="chat:retry-reset",
        chat_id="chat",
        message_id=101,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="retry reset",
        caption="",
        content_kind="text",
        raw_message={"message_id": 101},
    )
    store.mark_capture_failed(capture_id, error="temporary codex failure")

    store.mark_capture_processed(capture_id)

    row = store.get_capture(capture_id)
    assert row is not None
    assert row["status"] == "processed"
    assert row["retry_count"] == 0
    assert row["next_retry_at"] == ""
    assert row["last_error"] == ""


def test_list_capture_summaries_filters_by_primary_or_secondary_interest(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    first_id = store.add_capture(
        capture_key="chat:3",
        chat_id="chat",
        message_id=3,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="AI 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 3},
    )
    second_id = store.add_capture(
        capture_key="chat:4",
        chat_id="chat",
        message_id=4,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="운동 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 4},
    )
    store.upsert_archive_item(
        first_id,
        {
            "title": "AI 글",
            "core_summary": "AI 요약",
            "raw_extracted_text": "AI 글",
            "source_language": "ko",
            "primary_interest": "AI",
            "secondary_interests": ["career"],
            "topic": "agents",
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    store.upsert_archive_item(
        second_id,
        {
            "title": "운동 글",
            "core_summary": "운동 요약",
            "raw_extracted_text": "운동 글",
            "source_language": "ko",
            "primary_interest": "health",
            "secondary_interests": ["lifestyle"],
            "topic": "training",
            "confidence": 0.8,
            "needs_review": False,
        },
    )

    ai_rows = store.list_capture_summaries(10, interest="AI")
    career_rows = store.list_capture_summaries(10, interest="career")

    assert [row["id"] for row in ai_rows] == [first_id]
    assert [row["id"] for row in career_rows] == [first_id]
