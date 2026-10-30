from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from dalife import cli
from dalife.cli import main
from dalife.config import Settings, read_env_values
from dalife.storage import ArchiveStore


def test_doctor_offline_allows_missing_telegram_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("DALIFE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("DALIFE_MEDIA_DIR", str(tmp_path / "captures"))
    monkeypatch.setenv("DALIFE_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("DALIFE_CODEX_BIN", "python3")
    monkeypatch.setenv("DALIFE_CODEX_ENABLED", "false")

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "TELEGRAM_BOT_TOKEN is missing" in output
    assert "sqlite:" in output


def test_setup_cmd_writes_env_without_printing_secret(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env"
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.setattr(cli, "get_settings", lambda: make_cli_settings(tmp_path, token="secret-token", chat_ids=("-100123",)))
    monkeypatch.setattr(cli, "run_doctor", lambda settings, store, online=False: (0, "[OK] doctor"))

    assert (
        cli.setup_cmd(
            settings,
            dry_run=False,
            non_interactive=True,
            telegram_bot_token="secret-token",
            telegram_chat_id="-100123",
            telegram_admin_user_id="42",
            allow_all_chats=False,
            install_launchd=False,
        )
        == 0
    )

    assert "secret-token" in env_file.read_text(encoding="utf-8")
    assert "secret-token" not in capsys.readouterr().out


def test_setup_cmd_preserves_existing_food_provider_config(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("KAKAO_REST_API_KEY=keep-provider-key\n", encoding="utf-8")
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "run_doctor", lambda settings, store, online=False: (0, "[OK] doctor"))

    assert cli.setup_cmd(
        settings,
        dry_run=False,
        non_interactive=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
        telegram_admin_user_id="42",
        allow_all_chats=False,
        install_launchd=False,
    ) == 0

    assert "KAKAO_REST_API_KEY=keep-provider-key" in env_file.read_text(encoding="utf-8")


def test_setup_accepts_momuk_provider_options_without_printing_secrets(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env"
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "run_doctor", lambda settings, store, online=False: (0, "[OK] doctor"))

    assert main([
        "setup", "--non-interactive",
        "--telegram-bot-token", "telegram-secret",
        "--telegram-allowed-chat-ids", "123",
        "--telegram-admin-user-ids", "42",
        "--kakao-rest-api-key", "kakao-secret",
        "--naver-client-id", "naver-id",
        "--naver-client-secret", "naver-secret",
        "--codex-bin", "/opt/local/bin/codex",
    ]) == 0

    values = read_env_values(env_file)
    assert values["KAKAO_REST_API_KEY"] == "kakao-secret"
    assert values["NAVER_CLIENT_SECRET"] == "naver-secret"
    assert values["DALIFE_CODEX_BIN"] == "/opt/local/bin/codex"
    output = capsys.readouterr().out
    assert "telegram-secret" not in output
    assert "kakao-secret" not in output
    assert "naver-secret" not in output


def test_send_test_requires_exactly_one_target(capsys):
    settings = make_cli_settings(__import__("pathlib").Path("/tmp"), token="token", chat_ids=("123",))

    assert cli.send_test_cmd(settings, chat_id=None, use_registered=False, use_allowed=False, dry_run=True) == 2
    assert "choose exactly one target" in capsys.readouterr().out

    assert cli.send_test_cmd(settings, chat_id=None, use_registered=False, use_allowed=True, dry_run=True) == 0
    assert "would send test message to ***" in capsys.readouterr().out


def test_rooms_reports_registered_room(tmp_path, capsys, monkeypatch):
    settings = make_cli_settings(tmp_path, chat_ids=())
    settings.state_dir.mkdir(parents=True)
    (settings.state_dir / "telegram_rooms.json").write_text(
        json.dumps({"dalife_chat_id": "-100123", "dalife_chat_title": "archive"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["rooms"]) == 0
    output = capsys.readouterr().out
    assert "dalife_chat_id=***0123" in output
    assert "allowed=yes" in output


def test_pending_shows_dry_run_processor_context(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path, codex_enabled=True)
    store = ArchiveStore(settings.state_dir)
    store.add_capture(
        capture_key="chat:1",
        chat_id="chat",
        message_id=1,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="관심 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 1},
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "pending"]) == 0
    output = capsys.readouterr().out
    assert "dry-run processor=codex kind=text files=0" in output
    assert "관심 글" in output


def test_list_shows_file_and_archive_status(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    capture_id = store.add_capture(
        capture_key="chat:2",
        chat_id="chat",
        message_id=2,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="관심 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 2},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "정리된 제목",
            "core_summary": "스크린샷 안의 핵심 요약",
            "key_points": ["핵심 1"],
            "context": "screenshot",
            "raw_extracted_text": "관심 글",
            "why_saved": "참고할 만한 내용",
            "source_language": "ko",
            "tags": [],
            "primary_interest": "AI",
            "secondary_interests": ["career"],
            "topic": "agents",
            "subtopic": "personal archive",
            "classification_reason": "AI archive workflow",
            "revisit_priority": "high",
            "revisit_reason": "제품 방향에 참고",
            "insight_seed": "AI와 개인 아카이브 연결",
            "dates_mentioned": [],
            "people_mentioned": [],
            "action_candidates": [],
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "list"]) == 0
    output = capsys.readouterr().out
    assert "files=none" in output
    assert "archive=archived" in output
    assert "interest=AI topic=agents" in output
    assert "정리된 제목" in output


def test_list_filters_by_interest(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    capture_id = store.add_capture(
        capture_key="chat:21",
        chat_id="chat",
        message_id=21,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="커리어 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 21},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "커리어 글",
            "core_summary": "커리어 요약",
            "raw_extracted_text": "커리어 글",
            "source_language": "ko",
            "primary_interest": "career",
            "secondary_interests": ["AI"],
            "topic": "portfolio",
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "list", "--interest", "AI"]) == 0
    output = capsys.readouterr().out
    assert capture_id in output
    assert "interest=career topic=portfolio" in output


def test_search_command_returns_explained_matches(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    capture_id = add_archive_item(
        store,
        message_id=31,
        title="Local archive retrieval",
        primary_interest="AI",
        secondary_interests=["product"],
        topic="search",
        tags=["fts", "archive"],
        raw_text="SQLite FTS makes saved captures searchable.",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "search", "SQLite", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["query"] == "SQLite"
    assert payload["results"][0]["capture_id"] == capture_id
    assert "extracted_text" in payload["results"][0]["matched_fields"]
    assert payload["results"][0]["match_explanation"].startswith("Matched")


def test_search_command_can_rebuild_generated_index(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    add_archive_item(
        store,
        message_id=32,
        title="Search index rebuild",
        primary_interest="AI",
        secondary_interests=[],
        topic="search",
        tags=["fts"],
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "search", "rebuild", "--rebuild"]) == 0
    output = capsys.readouterr().out

    assert "search index rebuilt archive_items=1" in output
    assert "why: Matched" in output


def test_archive_group_list_search_and_show_commands(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    capture_id = add_archive_item(
        store,
        message_id=35,
        title="Grouped archive command",
        primary_interest="AI",
        secondary_interests=["product"],
        topic="cli",
        tags=["archive"],
        raw_text="Grouped archive search alias keeps behavior compatible.",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "list", "--json"]) == 0
    list_payload = json.loads(capsys.readouterr().out)
    assert list_payload[0]["id"] == capture_id

    assert main(["archive", "search", "Grouped", "--json"]) == 0
    search_payload = json.loads(capsys.readouterr().out)
    assert search_payload["query"] == "Grouped"
    assert search_payload["results"][0]["capture_id"] == capture_id

    assert main(["archive", "show", capture_id, "--json"]) == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["archive_item"]["title"] == "Grouped archive command"


def test_review_command_lists_needs_review_and_revisit_queues(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    review_id = add_archive_item(
        store,
        message_id=33,
        title="Weak classification",
        primary_interest="other/unknown",
        secondary_interests=[],
        topic="",
        tags=[],
        needs_review=True,
    )
    revisit_id = add_archive_item(
        store,
        message_id=34,
        title="Useful project seed",
        primary_interest="product",
        secondary_interests=[],
        topic="archive",
        tags=["idea"],
        needs_review=False,
        insight_seed="turn this into a retrieval workflow",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "review", "--needs-review", "--json"]) == 0
    needs_review = json.loads(capsys.readouterr().out)
    assert needs_review["mode"] == "needs-review"
    assert [item["capture_id"] for item in needs_review["items"]] == [review_id]

    assert main(["archive", "review", "--revisit", "--json"]) == 0
    revisit = json.loads(capsys.readouterr().out)
    assert revisit["mode"] == "revisit"
    assert revisit_id in [item["capture_id"] for item in revisit["items"]]


def test_food_plan_collection_command_can_persist_query_ledger(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["food", "plan-collection", "--area", "신정동", "--alias", "목동역", "--daily-quota-limit", "4", "--persist", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["area"] == "신정동"
    assert result["quota_cost"] == 4
    assert len(result["persisted"]) == 4

    assert main(["food", "due-queries", "--due-at", "2999-01-01T00:00:00+00:00", "--json"]) == 0
    due = json.loads(capsys.readouterr().out)
    assert len(due) == 4
    assert {row["domain"] for row in due} == {"food"}


def test_food_parse_command_exposes_native_parser_without_provider_calls(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["food", "parse", "오목교역 곱창 맛집 3곳 추천", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result == {
        "intent": "start",
        "area": "오목교역",
        "topic": "곱창",
        "meal_type": "",
        "budget": "",
        "occasion": "",
        "count": 3,
        "needs_location": False,
    }

    assert main(["food", "parse", "내 주변 야식 맛집 추천"]) == 0
    output = capsys.readouterr().out
    assert "intent=needs_location" in output
    assert "meal_type=야식" in output


def test_food_recommend_local_command_ranks_sqlite_candidates_and_audits_session(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao_local",
        provider_place_id="20551759",
        name="미성참숯정육식당",
        normalized_name="미성참숯정육식당",
        area_id=area["id"],
        category="고기",
        road_address="서울 양천구 신정중앙로 70",
        map_url="https://place.map.kakao.com/20551759",
    )
    evidence = store.upsert_evidence_item(
        provider="naver_blog",
        url="https://blog.example/meat",
        title="신정동 고기 저녁 후기",
        snippet="숯불고기",
        author="local-author",
    )
    store.link_place_evidence(
        place_id=place["id"],
        evidence_item_id=evidence["id"],
        match_type="exact_name",
        score=0.91,
        decision="matched",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["food", "recommend-local", "--area", "신정동", "--topic", "고기 저녁", "--count", "5", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["requested_count"] == 5
    assert result["returned_count"] == 1
    assert result["session_id"]
    assert result["places"][0]["name"] == "미성참숯정육식당"
    assert result["places"][0]["evidence_tier"] == "partial"
    assert result["places"][0]["evidence"][0]["url"] == "https://blog.example/meat"


def test_food_recommend_local_dry_run_does_not_persist_session(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    store.upsert_place(
        provider="kakao_local",
        provider_place_id="dry-place",
        name="Dry Run Place",
        normalized_name="dryrunplace",
        area_id=area["id"],
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main([
        "food", "recommend-local", "--area", "신정동", "--dry-run", "--json",
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["session_id"] == ""
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM recommendation_sessions").fetchone()[0] == 0


def test_food_run_collection_dry_run_respects_configured_provider_and_does_not_call_api(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = replace(make_cli_settings(tmp_path), kakao_rest_api_key="configured")
    store = ArchiveStore(settings.state_dir)
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    query = store.upsert_query_ledger_entry(
        domain="food",
        provider="kakao_local",
        query_text="신정동 맛집",
        area_id=area["id"],
        facet="broad_discovery",
        sort_mode="accuracy",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["food", "run-collection", "--max-queries", "1", "--dry-run", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True
    assert result["items"] == [
        {
            "ledger_id": query["id"],
            "provider": "kakao_local",
            "query_text": "신정동 맛집",
            "status": "dry_run",
            "yielded_count": 0,
            "places_stored": 0,
            "evidence_stored": 0,
            "evidence_links": 0,
            "new_places_count": 0,
            "refreshed_places_count": 0,
            "new_evidence_count": 0,
            "duplicate_evidence_count": 0,
            "high_quality_links_count": 0,
            "unmatched_evidence_count": 0,
            "failure_reason": "",
            "quota_cost": 1,
        }
    ]
    assert store.list_places(area_id=area["id"]) == []


def test_life_preview_command_preserves_default_due_reminders(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "preview", "--date", "2026-08-30", "--time", "20:00", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert [item["reminder_id"] for item in result] == ["trash-2026-08-30"]
    assert "생활알림 | 분리수거" in result[0]["message"]


def test_life_list_command_exposes_imported_default_catalog(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "list", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    ids = [item["reminder_id"] for item in result]
    assert ids[:4] == ["haircut", "fingernails", "toenails", "trash"]
    assert result[0]["title"] == "미용실 예약"
    assert result[0]["requires_confirmation"] is True
    assert {"label": "예약했음", "choice": "yes"} in result[0]["interaction_labels"]


def test_life_next_command_lists_upcoming_default_reminders(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "next", "--date", "2026-08-29", "--time", "00:00", "--days", "2", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    ids = [item["reminder_id"] for item in result]
    assert "mac-status-2026-08-29" in ids
    assert "weekend-cleaning-2026-08-29" in ids
    assert "trash-2026-08-30" in ids


def test_life_run_once_dry_run_uses_sqlite_without_creating_events(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path, token="token", chat_ids=("123",))
    store = ArchiveStore(settings.state_dir)
    routine = store.upsert_routine(routine_key="trash", title="Trash", description="")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="trash",
        title="Trash",
        cadence="trash",
        schedule={"time": "20:00", "weekdays": ["sun"]},
        action="Take out trash",
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "run-once", "--date", "2026-08-30", "--time", "20:00", "--dry-run", "--json"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["due"] == 1
    assert result["sent"] == 0
    assert store.list_due_reminder_events(due_at="9999-12-31T00:00:00+00:00") == []


def test_life_run_once_sends_due_sqlite_event_once(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path, token="token", chat_ids=("123",))
    store = ArchiveStore(settings.state_dir)
    routine = store.upsert_routine(routine_key="trash", title="Trash", description="")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="trash",
        title="Trash",
        cadence="trash",
        schedule={"time": "20:00", "weekdays": ["sun"]},
        action="Take out trash",
    )

    class Api:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_markup=None):
            self.messages.append((chat_id, text, reply_markup))
            return {"result": {"message_id": len(self.messages)}}

    api = Api()
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "TelegramApiClient", lambda token: api)
    args = ["life", "run-once", "--date", "2026-08-30", "--time", "20:00", "--json"]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)

    assert (first["due"], first["sent"]) == (1, 1)
    assert (second["due"], second["sent"]) == (0, 0)
    assert len(api.messages) == 1


def test_life_native_management_commands_round_trip_custom_reminder(
    tmp_path,
    monkeypatch,
    capsys,
):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main([
        "life", "add", "custom",
        "--id", "water-plants",
        "--title", "Water plants",
        "--kind", "weekly",
        "--time", "09:30",
        "--weekday", "sun",
        "--action", "Water plants",
    ]) == 0
    assert "added water-plants" in capsys.readouterr().out

    assert main(["life", "show", "water-plants", "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["weekday"] == "sun"

    assert main(["life", "update", "water-plants", "--time", "10:15", "--title", "Water all plants"]) == 0
    capsys.readouterr()
    assert main(["life", "disable", "water-plants"]) == 0
    capsys.readouterr()
    assert main(["life", "validate"]) == 0
    assert "valid" in capsys.readouterr().out

    assert main(["life", "show", "water-plants", "--json"]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["time"] == "10:15"
    assert updated["title"] == "Water all plants"
    assert updated["enabled"] is False

    assert main(["life", "remove", "water-plants"]) == 0
    assert "removed water-plants" in capsys.readouterr().out


def test_life_native_management_rejects_invalid_custom_schedule(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main([
        "life", "add", "custom",
        "--id", "water-plants",
        "--title", "Water plants",
        "--kind", "weekly",
        "--time", "25:00",
        "--weekday", "sun",
        "--action", "Water plants",
    ]) == 1
    assert "time must be HH:MM" in capsys.readouterr().out


def test_life_pending_answer_and_interactions_use_sqlite_events(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    routine = store.upsert_routine(routine_key="haircut", title="Haircut")
    reminder = store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="haircut",
        title="Haircut",
        cadence="haircut",
        schedule={},
        action="Book haircut",
        requires_confirmation=True,
    )
    event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="life:haircut:test",
        due_at="2026-09-01T08:45:00+09:00",
        status="pending_confirmation",
        response_payload={
            "title": "Haircut",
            "prompt": "Booked?",
            "actions": ["yes", "no"],
            "followup_days": 7,
        },
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "pending", "--json"]) == 0
    pending = json.loads(capsys.readouterr().out)
    assert pending[0]["id"] == event["id"]

    assert main(["life", "answer", event["id"], "yes"]) == 0
    assert "recorded yes" in capsys.readouterr().out
    assert main(["life", "interactions", "--json"]) == 0
    interactions = json.loads(capsys.readouterr().out)
    assert interactions[0]["status"] == "completed"
    assert interactions[0]["selected_response"] == "yes"


def test_life_pattern_commands_persist_and_render_from_sqlite(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["life", "pattern", "set", "--prefix", "내 알림", "--action-label", "할 일"]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["prefix"] == "내 알림"

    assert main(["life", "pattern", "show"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown == updated

    assert main(["life", "preview", "--date", "2026-08-30", "--time", "20:00", "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert "내 알림 | 분리수거" in preview[0]["message"]
    assert "할 일" in preview[0]["message"]


def test_course_plan_command_can_persist_draft(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert (
        main(
            [
                "course",
                "plan",
                "--title",
                "이태원 저녁 코스",
                "--area",
                "이태원",
                "--date",
                "2026-08-29",
                "--time",
                "18:00",
                "--persist",
                "--json",
            ]
        )
        == 0
    )

    result = json.loads(capsys.readouterr().out)
    assert result["title"] == "이태원 저녁 코스"
    assert result["stored"]["title"] == "이태원 저녁 코스"
    assert result["stops"] == []


def test_schedule_plan_command_lists_unified_jobs(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["schedule", "plan", "--json"]) == 0

    rows = json.loads(capsys.readouterr().out)
    names = {row["name"] for row in rows}
    assert "telegram" in names
    assert "archive-process" in names
    assert "food-collect" in names
    assert "life-send" in names
    assert "course-suggestions" not in names

    assert main(["schedule", "plan", "--include-disabled", "--json"]) == 0
    all_rows = json.loads(capsys.readouterr().out)
    assert "course-suggestions" in {row["name"] for row in all_rows}


def test_show_displays_structured_archive_item(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    capture_id = store.add_capture(
        capture_key="chat:22",
        chat_id="chat",
        message_id=22,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="",
        caption="",
        content_kind="photo",
        raw_message={"message_id": 22},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "스크린샷 제목",
            "core_summary": "이미지 안의 실제 핵심",
            "key_points": ["중요한 주장"],
            "context": "social post screenshot",
            "raw_extracted_text": "보이는 텍스트",
            "why_saved": "나중에 참고할 아이디어",
            "source_language": "ko",
            "tags": ["idea"],
            "primary_interest": "AI",
            "secondary_interests": ["career", "technology"],
            "topic": "agents",
            "subtopic": "archive workflow",
            "classification_reason": "agent-based archive idea",
            "revisit_priority": "high",
            "revisit_reason": "DaLife 제품 방향과 연결됨",
            "insight_seed": "captures can become agent-readable knowledge",
            "dates_mentioned": [],
            "people_mentioned": [],
            "action_candidates": [],
            "confidence": 0.8,
            "needs_review": False,
        },
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "show", capture_id]) == 0
    output = capsys.readouterr().out
    assert "archive_title: 스크린샷 제목" in output
    assert "core_summary: 이미지 안의 실제 핵심" in output
    assert "key_point: 중요한 주장" in output
    assert "why_saved: 나중에 참고할 아이디어" in output
    assert "primary_interest: AI" in output
    assert "secondary_interests: career, technology" in output
    assert "topic: agents" in output
    assert "classification_reason: agent-based archive idea" in output
    assert "revisit_priority: high" in output
    assert "insight_seed: captures can become agent-readable knowledge" in output


def test_process_prints_progress(tmp_path, monkeypatch, capsys):
    settings = make_cli_settings(tmp_path, codex_enabled=False)
    store = ArchiveStore(settings.state_dir)
    store.add_capture(
        capture_key="chat:3",
        chat_id="chat",
        message_id=3,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="처리할 글",
        caption="",
        content_kind="text",
        raw_message={"message_id": 3},
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    assert main(["archive", "process", "--no-codex"]) == 0
    output = capsys.readouterr().out
    assert "[process:start]" in output
    assert "[process:done]" in output
    assert "elapsed=" in output


def test_processed_capture_prompt_is_sent_without_manual_command(tmp_path, monkeypatch):
    settings = make_cli_settings(tmp_path, token="token", chat_ids=("123",))
    store = ArchiveStore(settings.state_dir)
    capture_id = add_archive_item(
        store,
        message_id=1003,
        title="Weak classification item",
        primary_interest="other/unknown",
        secondary_interests=[],
        topic="",
        tags=[],
        confidence=0.2,
        needs_review=True,
    )
    store.mark_capture_processed(capture_id)
    fake_api = FakeDigestTelegramApi()
    monkeypatch.setattr(cli, "TelegramApiClient", lambda token: fake_api)

    sent = cli.send_processed_capture_prompts(settings, store, [{"status": "processed", "capture_id": capture_id}])

    assert len(sent) == 1
    assert len(fake_api.messages) == 1
    assert "Weak classification item" in fake_api.messages[0]["text"]
    keyboard = fake_api.messages[0]["reply_markup"]["inline_keyboard"]
    assert any(button["text"] == "Needs review" for row in keyboard for button in row)


def add_archive_item(
    store: ArchiveStore,
    *,
    message_id: int,
    title: str,
    primary_interest: str,
    secondary_interests: list[str],
    topic: str,
    tags: list[str],
    classification_reason: str = "classified by test",
    confidence: float = 0.8,
    needs_review: bool = False,
    key_points: list[str] | None = None,
    insight_seed: str = "connect later",
    revisit_reason: str = "",
    raw_text: str | None = None,
) -> str:
    capture_id = store.add_capture(
        capture_key=f"chat:{message_id}",
        chat_id="chat",
        message_id=message_id,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text=title,
        caption="",
        content_kind="text",
        raw_message={"message_id": message_id},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": title,
            "core_summary": f"{title} summary",
            "key_points": [f"{title} point"] if key_points is None else key_points,
            "raw_extracted_text": title if raw_text is None else raw_text,
            "source_language": "en",
            "primary_interest": primary_interest,
            "secondary_interests": secondary_interests,
            "topic": topic,
            "tags": tags,
            "classification_reason": classification_reason,
            "revisit_priority": "medium",
            "revisit_reason": revisit_reason,
            "insight_seed": insight_seed,
            "confidence": confidence,
            "needs_review": needs_review,
        },
    )
    return capture_id


class FakeDigestTelegramApi:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send_message(self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return {"result": {"message_id": len(self.messages)}}


def make_cli_settings(
    tmp_path,
    *,
    token: str = "",
    chat_ids: tuple[str, ...] = (),
    codex_enabled: bool = False,
) -> Settings:
    return Settings(
        root=tmp_path,
        telegram_bot_token=token,
        telegram_allowed_chat_ids=chat_ids,
        telegram_admin_user_ids=("42",),
        telegram_allow_all_chats=False,
        state_dir=tmp_path / ".local" / "state",
        log_dir=tmp_path / ".local" / "logs",
        media_dir=tmp_path / ".local" / "captures",
        codex_enabled=codex_enabled,
        codex_bin="python3",
        codex_model="",
        codex_sandbox="read-only",
        codex_ephemeral=True,
        codex_timeout_sec=30,
        processor_batch_size=10,
        tesseract_bin="tesseract",
    )
