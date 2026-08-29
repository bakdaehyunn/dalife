from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
from typing import Any

from darchivebot.archive_values import archive_item_to_dict, json_string_list as load_json_list, record_to_dict as row_to_dict
from darchivebot.config import DEFAULT_ENV_FILE, ROOT, Settings, ensure_local_dirs, get_settings, load_env
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
        return setup_cmd(
            settings,
            dry_run=args.dry_run,
            non_interactive=args.non_interactive,
            telegram_bot_token=args.telegram_bot_token,
            telegram_chat_id=args.telegram_chat_id,
            telegram_admin_user_id=args.telegram_admin_user_id,
            allow_all_chats=args.allow_all_chats,
            install_launchd=args.install_launchd,
        )
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
    if args.cmd == "web":
        return web_cmd(store, host=args.host, port=args.port)
    if args.cmd == "interests":
        return interests_cmd(store, limit=args.limit, json_output=args.json)
    if args.cmd == "concepts":
        return concepts_cmd(store, limit=args.limit, json_output=args.json)
    if args.cmd == "related":
        return related_cmd(store, capture_id=args.capture_id, limit=args.limit, json_output=args.json)
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
) -> int:
    """Compatibility wrapper preserving injectable CLI module dependencies."""
    return setup_cmd_impl(
        settings,
        dry_run=dry_run,
        non_interactive=non_interactive,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        telegram_admin_user_id=telegram_admin_user_id,
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
