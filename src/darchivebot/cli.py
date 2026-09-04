from __future__ import annotations

import argparse
import getpass
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from darchivebot.archive_values import archive_item_to_dict, json_string_list as load_json_list, record_to_dict as row_to_dict
from darchivebot.config import DEFAULT_ENV_FILE, ROOT, Settings, ensure_local_dirs, get_settings, load_env
from darchivebot.cutover import cutover_report, inspect_launchd
from darchivebot.doctor import run_doctor
from darchivebot.graph import default_graph_path, export_graph as export_jsonld_graph
from darchivebot.insights import generate_insight_note, list_insight_notes, show_insight_note
from darchivebot.bot_prompts import (
    create_post_process_prompt,
    create_project_seed_digest_prompt,
    create_revisit_digest_prompt,
    create_weekly_insight_prompt,
)
from darchivebot.cli_parser import build_parser
from darchivebot.cli_commands.setup import init_cmd, setup_cmd_impl
from darchivebot.cli_commands.telegram import (
    discover_chat_cmd,
    send_processed_capture_prompts_impl,
    send_test_cmd,
    telegram_commands_cmd,
    telegram_digest_cmd_impl,
)
from darchivebot.cli_commands.archive import (
    concepts_cmd,
    insights_cmd,
    interests_cmd,
    list_cmd,
    related_cmd,
    reprocess_cmd,
    reprocess_dry_run_cmd,
    reprocess_plan_cmd,
    review_cmd,
    search_cmd,
    show_cmd,
    web_cmd,
)
from darchivebot.cli_commands.graph import graph_cmd
from darchivebot.cli_commands.personal import course_cmd, food_cmd, life_cmd
from darchivebot.cli_formatting import (
    format_classification_preview,
    format_file_status,
    format_process_and_graph_results,
    format_search_label,
    mask_identifier,
    only_allowed_chat_id,
    print_process_progress,
)
from darchivebot.processor import CaptureProcessor, format_results
from darchivebot.readiness import (
    ISSUE_NAMES,
    concept_summary,
    graph_quality_summary,
    interest_summary,
    related_captures,
    reprocess_plan,
)
from darchivebot.search import rebuild_search_index, review_queue, search_archive
from darchivebot.semantic_graph import (
    default_semantic_export_path,
    default_semantic_store_path,
    export_semantic_store,
    init_semantic_store,
    semantic_store_stats,
    sync_semantic_store,
)
from darchivebot.scheduler import schedule_summary
from darchivebot.storage import ArchiveStore
from darchivebot.telegram import (
    DEFAULT_BOT_COMMANDS,
    REGISTERED_CHAT_BOT_COMMANDS,
    TelegramApiClient,
    TelegramCaptureBot,
    chat_command_scope,
    discover_chat_candidates,
    format_rooms_report,
    read_room_state,
    send_bot_prompt,
)
from darchivebot.web import serve_local_web


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    args = parser.parse_args(argv)
    load_env()
    settings = get_settings()
    store = ArchiveStore(settings.state_dir)

    if args.cmd == "init":
        return init_cmd(settings, store)
    if args.cmd == "setup":
        code = setup_cmd(
            settings,
            dry_run=args.dry_run,
            non_interactive=args.non_interactive,
            telegram_bot_token=args.telegram_bot_token,
            telegram_chat_id=args.telegram_chat_id,
            telegram_admin_user_id=args.telegram_admin_user_id,
            timezone=args.timezone,
            naver_client_id=args.naver_client_id,
            naver_client_secret=args.naver_client_secret,
            kakao_rest_api_key=args.kakao_rest_api_key,
            codex_bin=args.codex_bin,
            allow_all_chats=args.allow_all_chats,
            install_launchd=args.install_launchd,
        )
        if code == 0 and args.sync_telegram_commands:
            return telegram_commands_cmd(get_settings(), "sync")
        return code
    if args.cmd == "doctor":
        code, text = run_doctor(settings, store, online=args.online)
        print(text)
        return code
    if args.cmd == "discover-chat":
        return discover_chat_cmd(settings, plain=args.plain, json_output=args.json)
    if args.cmd == "rooms":
        code, text = format_rooms_report(settings)
        print(text)
        return code
    if args.cmd == "telegram-commands":
        return telegram_commands_cmd(settings, args.telegram_commands_cmd)
    if args.cmd == "setup-telegram-commands":
        return telegram_commands_cmd(settings, "sync")
    if args.cmd == "send-test":
        return send_test_cmd(
            settings,
            chat_id=args.chat_id,
            use_registered=args.registered,
            use_allowed=args.allowed,
            dry_run=args.dry_run,
        )
    if args.cmd == "telegram":
        bot = TelegramCaptureBot(settings, store)
        bot.run_polling(poll_interval_sec=args.poll_interval_sec)
        return 0
    if args.cmd == "telegram-digest":
        return telegram_digest_cmd(
            settings,
            store,
            kind=args.kind,
            limit=args.limit,
            dry_run=args.dry_run,
            json_output=args.json,
        )
    if args.cmd == "process":
        processor = CaptureProcessor(settings, store)
        results = processor.process_pending(
            limit=args.limit,
            dry_run=args.dry_run,
            use_codex=False if args.no_codex else None,
            progress=None if args.json or args.dry_run else print_process_progress,
        )
        semantic_graph_result = None
        jsonld_graph_result = None
        if args.export_graph and not args.dry_run and any(item.get("status") == "processed" for item in results):
            semantic_graph_result = sync_semantic_store(store, default_semantic_store_path(settings.root))
            jsonld_graph_result = export_jsonld_graph(store, default_graph_path(settings.root))
        if not args.dry_run:
            send_processed_capture_prompts(settings, store, results)
        print(
            format_process_and_graph_results(
                results,
                semantic_graph_result=semantic_graph_result,
                jsonld_graph_result=jsonld_graph_result,
                json_output=args.json,
            )
        )
        return 0 if not any(item.get("status") == "failed" for item in results) else 1
    if args.cmd == "pending":
        processor = CaptureProcessor(settings, store)
        results = processor.process_pending(
            limit=args.limit,
            dry_run=True,
            use_codex=False if args.no_codex else None,
        )
        print(format_results(results, json_output=args.json))
        return 0
    if args.cmd == "reprocess-plan":
        return reprocess_plan_cmd(
            store,
            limit=args.limit,
            issue=args.issue or "",
            fallback_only=args.fallback_only,
            needs_review_only=args.needs_review_only,
            capture_id=args.capture_id or "",
            json_output=args.json,
        )
    if args.cmd == "reprocess":
        if args.dry_run:
            return reprocess_dry_run_cmd(
                store,
                limit=args.limit,
                issue=args.issue or "",
                fallback_only=args.fallback_only,
                needs_review_only=args.needs_review_only,
                capture_id=args.capture_id or "",
                json_output=args.json,
            )
        return reprocess_cmd(
            settings,
            store,
            capture_id=args.capture_id or "",
            use_codex=False if args.no_codex else None,
            export_graph=not args.no_export_graph,
            json_output=args.json,
        )
    if args.cmd == "list":
        return list_cmd(store, limit=args.limit, interest=args.interest or "", json_output=args.json)
    if args.cmd == "search":
        return search_cmd(
            store,
            query=args.query,
            limit=args.limit,
            rebuild=args.rebuild,
            json_output=args.json,
        )
    if args.cmd == "review":
        return review_cmd(
            store,
            limit=args.limit,
            needs_review_only=args.needs_review,
            revisit_only=args.revisit,
            json_output=args.json,
        )
    if args.cmd == "archive":
        return archive_cmd(settings, store, args)
    if args.cmd == "web":
        return web_cmd(store, host=args.host, port=args.port)
    if args.cmd == "interests":
        return interests_cmd(store, limit=args.limit, json_output=args.json)
    if args.cmd == "concepts":
        return concepts_cmd(store, limit=args.limit, json_output=args.json)
    if args.cmd == "related":
        return related_cmd(store, capture_id=args.capture_id, limit=args.limit, json_output=args.json)
    if args.cmd == "food":
        return food_cmd(
            settings,
            store,
            action=args.food_cmd,
            area=getattr(args, "area", ""),
            aliases=getattr(args, "alias", []),
            legacy_areas=getattr(args, "legacy_area", []),
            place_limit=getattr(args, "place_limit", 20),
            daily_quota_limit=getattr(args, "daily_quota_limit", 30),
            default_count=getattr(args, "default_count", 30),
            text=getattr(args, "text", ""),
            persist=getattr(args, "persist", False),
            due_at=getattr(args, "due_at", ""),
            limit=getattr(args, "limit", 20),
            topic=getattr(args, "topic", ""),
            occasion=getattr(args, "occasion", ""),
            count=getattr(args, "count", 10),
            avoid_terms=getattr(args, "avoid", []),
            required_terms=getattr(args, "require", []),
            latitude=getattr(args, "latitude", None),
            longitude=getattr(args, "longitude", None),
            max_queries=getattr(args, "max_queries", 20),
            max_quota_cost=getattr(args, "max_quota_cost", 20),
            dry_run=getattr(args, "dry_run", False),
            source_env=getattr(args, "source_env", None),
            source_root=getattr(args, "root", None),
            overwrite=getattr(args, "overwrite", False),
            json_output=args.json,
        )
    if args.cmd == "life":
        return life_cmd(
            settings,
            store,
            action=args.life_cmd,
            date_text=getattr(args, "date", ""),
            time_text=getattr(args, "time", ""),
            days=getattr(args, "days", 7),
            source_root=getattr(args, "root", None),
            reminder_id=getattr(args, "id", ""),
            add_kind=getattr(args, "life_add_kind", ""),
            title=getattr(args, "title", None),
            reminder_kind=getattr(args, "kind", None),
            reminder_time=getattr(args, "time", None),
            reminder_action=getattr(args, "action", None),
            note=getattr(args, "note", None),
            reminder_date=getattr(args, "date", None),
            weekday=getattr(args, "weekday", None),
            base_date=getattr(args, "base_date", None),
            interval_days=getattr(args, "days", None),
            confirmation_id=getattr(args, "confirmation_id", ""),
            confirmation_answer=getattr(args, "answer", ""),
            pattern_action=getattr(args, "life_pattern_cmd", ""),
            pattern_prefix=getattr(args, "prefix", None),
            pattern_schedule_label=getattr(args, "schedule_label", None),
            pattern_action_label=getattr(args, "action_label", None),
            pattern_note_label=getattr(args, "note_label", None),
            dry_run=getattr(args, "dry_run", False),
            json_output=getattr(args, "json", False),
            api_factory=TelegramApiClient,
        )
    if args.cmd == "course":
        return course_cmd(
            store,
            action=args.course_cmd,
            title=args.title,
            area=args.area,
            date_text=args.date,
            time_text=args.time,
            persist=args.persist,
            json_output=args.json,
        )
    if args.cmd == "schedule":
        if args.schedule_cmd == "cutover-check":
            return schedule_cutover_cmd(settings, store, json_output=args.json)
        return schedule_cmd(include_disabled=args.include_disabled, json_output=args.json)
    if args.cmd == "insights":
        return insights_cmd(
            store,
            action=args.insights_cmd or "list",
            period=getattr(args, "period", "weekly"),
            dry_run=getattr(args, "dry_run", False),
            include_needs_review=getattr(args, "include_needs_review", False),
            limit=getattr(args, "limit", 20),
            insight_id=getattr(args, "insight_id", ""),
            json_output=args.json,
        )
    if args.cmd == "show":
        return show_cmd(store, capture_id=args.capture_id, json_output=args.json)
    if args.cmd == "graph":
        return graph_cmd(
            settings,
            store,
            action=args.graph_cmd,
            output_path=getattr(args, "output", None),
            stats_path=getattr(args, "path", None),
            limit=getattr(args, "limit", None),
            quality_limit=getattr(args, "limit", 20),
            include_raw_text=getattr(args, "include_raw_text", False),
            json_output=args.json,
        )
    return 2


def archive_cmd(settings: Settings, store: ArchiveStore, args: Any) -> int:
    if args.archive_cmd == "pending":
        processor = CaptureProcessor(settings, store)
        results = processor.process_pending(
            limit=args.limit,
            dry_run=True,
            use_codex=False if args.no_codex else None,
        )
        print(format_results(results, json_output=args.json))
        return 0
    if args.archive_cmd == "process":
        processor = CaptureProcessor(settings, store)
        results = processor.process_pending(
            limit=args.limit,
            dry_run=args.dry_run,
            use_codex=False if args.no_codex else None,
            progress=None if args.json or args.dry_run else print_process_progress,
        )
        semantic_graph_result = None
        jsonld_graph_result = None
        if args.export_graph and not args.dry_run and any(item.get("status") == "processed" for item in results):
            semantic_graph_result = sync_semantic_store(store, default_semantic_store_path(settings.root))
            jsonld_graph_result = export_jsonld_graph(store, default_graph_path(settings.root))
        if not args.dry_run:
            send_processed_capture_prompts(settings, store, results)
        print(
            format_process_and_graph_results(
                results,
                semantic_graph_result=semantic_graph_result,
                jsonld_graph_result=jsonld_graph_result,
                json_output=args.json,
            )
        )
        return 0 if not any(item.get("status") == "failed" for item in results) else 1
    if args.archive_cmd == "list":
        return list_cmd(store, limit=args.limit, interest=args.interest or "", json_output=args.json)
    if args.archive_cmd == "search":
        return search_cmd(
            store,
            query=args.query,
            limit=args.limit,
            rebuild=args.rebuild,
            json_output=args.json,
        )
    if args.archive_cmd == "review":
        return review_cmd(
            store,
            limit=args.limit,
            needs_review_only=args.needs_review,
            revisit_only=args.revisit,
            json_output=args.json,
        )
    if args.archive_cmd == "show":
        return show_cmd(store, capture_id=args.capture_id, json_output=args.json)
    if args.archive_cmd == "interests":
        return interests_cmd(store, limit=args.limit, json_output=args.json)
    if args.archive_cmd == "concepts":
        return concepts_cmd(store, limit=args.limit, json_output=args.json)
    if args.archive_cmd == "related":
        return related_cmd(store, capture_id=args.capture_id, limit=args.limit, json_output=args.json)
    return 2


def schedule_cmd(*, include_disabled: bool, json_output: bool) -> int:
    rows = schedule_summary(include_disabled=include_disabled)
    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    for row in rows:
        command = " ".join(str(part) for part in row["command"])
        enabled = "enabled" if row["enabled"] else "disabled"
        print(f"{row['name']}\t{enabled}\t{row['cadence']}\t{command}")
        print(f"  {row['purpose']}")
    return 0


def schedule_cutover_cmd(settings: Settings, store: ArchiveStore, *, json_output: bool) -> int:
    report = cutover_report(
        settings,
        store,
        snapshot=inspect_launchd(),
        now=datetime.now(ZoneInfo(settings.life_timezone)),
    )
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("READY" if report["ready"] else "BLOCKED")
        for check in report["checks"]:
            status = "PASS" if check["passed"] else "BLOCK"
            print(f"[{status}] {check['name']}")
            if check["remediation"]:
                print(f"  {check['remediation']}")
    return 0 if report["ready"] else 1


def setup_cmd(
    settings: Settings,
    *,
    dry_run: bool,
    non_interactive: bool,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    telegram_admin_user_id: str | None,
    allow_all_chats: bool,
    install_launchd: bool,
    timezone: str | None = None,
    naver_client_id: str | None = None,
    naver_client_secret: str | None = None,
    kakao_rest_api_key: str | None = None,
    codex_bin: str | None = None,
) -> int:
    """Compatibility wrapper preserving injectable CLI module dependencies."""
    return setup_cmd_impl(
        settings,
        dry_run=dry_run,
        non_interactive=non_interactive,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        telegram_admin_user_id=telegram_admin_user_id,
        timezone=timezone,
        naver_client_id=naver_client_id,
        naver_client_secret=naver_client_secret,
        kakao_rest_api_key=kakao_rest_api_key,
        codex_bin=codex_bin,
        allow_all_chats=allow_all_chats,
        install_launchd=install_launchd,
        env_file=DEFAULT_ENV_FILE,
        settings_loader=get_settings,
        doctor=run_doctor,
    )


def telegram_digest_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    kind: str,
    limit: int,
    dry_run: bool,
    json_output: bool,
) -> int:
    return telegram_digest_cmd_impl(
        settings,
        store,
        kind=kind,
        limit=limit,
        dry_run=dry_run,
        json_output=json_output,
        api_factory=TelegramApiClient,
    )


def send_processed_capture_prompts(
    settings: Settings,
    store: ArchiveStore,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return send_processed_capture_prompts_impl(
        settings,
        store,
        results,
        api_factory=TelegramApiClient,
    )


if __name__ == "__main__":
    raise SystemExit(main())
