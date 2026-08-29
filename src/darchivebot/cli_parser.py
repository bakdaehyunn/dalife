from __future__ import annotations

import argparse
from pathlib import Path

from darchivebot.readiness import ISSUE_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darchive")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create local config, state directories, and SQLite schema")

    p_setup = sub.add_parser("setup", help="Configure .env and optionally install launchd")
    p_setup.add_argument("--dry-run", action="store_true")
    p_setup.add_argument("--non-interactive", action="store_true")
    p_setup.add_argument("--telegram-bot-token")
    p_setup.add_argument("--telegram-chat-id")
    p_setup.add_argument("--telegram-admin-user-id")
    p_setup.add_argument("--allow-all-chats", action="store_true")
    p_setup.add_argument("--install-launchd", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Check local config and optional Telegram connectivity")
    p_doctor.add_argument("--online", action="store_true", help="Also call Telegram getMe when a token is configured")

    p_discover = sub.add_parser("discover-chat", help="Find Telegram chat ids from recent bot updates")
    p_discover.add_argument("--plain", action="store_true")
    p_discover.add_argument("--json", action="store_true")

    sub.add_parser("rooms", help="Show registered Telegram darchive room status")

    p_commands = sub.add_parser("telegram-commands", help="Show or sync Telegram command menu")
    commands_sub = p_commands.add_subparsers(dest="telegram_commands_cmd", required=True)
    commands_sub.add_parser("show", help="Show current Telegram command menu")
    commands_sub.add_parser("sync", help="Sync Telegram command menu")

    sub.add_parser("setup-telegram-commands", help=argparse.SUPPRESS)

    p_send_test = sub.add_parser("send-test", help="Send a test message")
    p_send_test.add_argument("--chat-id")
    p_send_test.add_argument("--registered", action="store_true", help="Use the registered darchive room")
    p_send_test.add_argument("--allowed", action="store_true", help="Use the only TELEGRAM_ALLOWED_CHAT_IDS value")
    p_send_test.add_argument("--dry-run", action="store_true")

    p_telegram = sub.add_parser("telegram", help="Run Telegram polling capture bot")
    p_telegram.add_argument("--poll-interval-sec", type=float, default=1.0)

    p_telegram_digest = sub.add_parser("telegram-digest", help="Send scheduled phone-first Telegram recommendation prompts")
    p_telegram_digest.add_argument("--kind", choices=["revisit", "project-seed", "weekly"], default="revisit")
    p_telegram_digest.add_argument("--limit", type=int, default=3)
    p_telegram_digest.add_argument("--dry-run", action="store_true")
    p_telegram_digest.add_argument("--json", action="store_true")

    p_process = sub.add_parser("process", help="Process pending captures into archive metadata")
    p_process.add_argument("--limit", type=int)
    p_process.add_argument("--dry-run", action="store_true")
    p_process.add_argument("--no-codex", action="store_true", help="Use the deterministic fallback processor")
    p_process.add_argument(
        "--export-graph",
        action="store_true",
        help="Refresh the semantic graph store and JSON-LD export after processing",
    )
    p_process.add_argument("--json", action="store_true")

    p_pending = sub.add_parser("pending", help="Preview pending captures and processor inputs")
    p_pending.add_argument("--limit", type=int)
    p_pending.add_argument("--no-codex", action="store_true")
    p_pending.add_argument("--json", action="store_true")

    p_reprocess_plan = sub.add_parser("reprocess-plan", help="Plan safe archive-quality reprocessing candidates")
    p_reprocess_plan.add_argument("--limit", type=int, default=20)
    p_reprocess_plan.add_argument("--issue", choices=ISSUE_NAMES)
    p_reprocess_plan.add_argument("--fallback-only", action="store_true")
    p_reprocess_plan.add_argument("--needs-review-only", action="store_true")
    p_reprocess_plan.add_argument("--capture-id")
    p_reprocess_plan.add_argument("--json", action="store_true")

    p_reprocess = sub.add_parser("reprocess", help="Reprocess one selected capture, or preview candidates with --dry-run")
    p_reprocess.add_argument("--capture-id")
    p_reprocess.add_argument("--limit", type=int, default=20)
    p_reprocess.add_argument("--issue", choices=ISSUE_NAMES)
    p_reprocess.add_argument("--fallback-only", action="store_true")
    p_reprocess.add_argument("--needs-review-only", action="store_true")
    p_reprocess.add_argument("--dry-run", action="store_true")
    p_reprocess.add_argument("--no-codex", action="store_true", help="Use the deterministic fallback processor")
    p_reprocess.add_argument("--no-export-graph", action="store_true", help="Do not refresh graph outputs after success")
    p_reprocess.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List recent captures")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--interest", help="Only show archived captures matching an interest")
    p_list.add_argument("--json", action="store_true")

    p_search = sub.add_parser("search", help="Search archived captures with the local SQLite FTS index")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--rebuild", action="store_true", help="Rebuild the generated FTS index before searching")
    p_search.add_argument("--json", action="store_true")

    p_review = sub.add_parser("review", help="List local archive items that need review or revisit")
    p_review.add_argument("--limit", type=int, default=20)
    p_review.add_argument("--needs-review", action="store_true")
    p_review.add_argument("--revisit", action="store_true")
    p_review.add_argument("--json", action="store_true")

    p_web = sub.add_parser("web", help="Run the local-only archive retrieval web UI")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8765)

    p_interests = sub.add_parser("interests", help="Inspect archive interest distribution")
    p_interests.add_argument("--limit", type=int, default=20)
    p_interests.add_argument("--json", action="store_true")

    p_concepts = sub.add_parser("concepts", help="Inspect archive concept/tag distribution")
    p_concepts.add_argument("--limit", type=int, default=20)
    p_concepts.add_argument("--json", action="store_true")

    p_related = sub.add_parser("related", help="Inspect read-only related captures from local graph signals")
    p_related.add_argument("capture_id")
    p_related.add_argument("--limit", type=int, default=10)
    p_related.add_argument("--json", action="store_true")

    p_insights = sub.add_parser("insights", help="List or generate local draft insight notes")
    p_insights.add_argument("--limit", type=int, default=20)
    p_insights.add_argument("--json", action="store_true")
    insights_sub = p_insights.add_subparsers(dest="insights_cmd")
    p_insights_generate = insights_sub.add_parser("generate", help="Generate a local draft insight note")
    p_insights_generate.add_argument("--period", choices=["weekly"], default="weekly")
    p_insights_generate.add_argument("--dry-run", action="store_true")
    p_insights_generate.add_argument("--include-needs-review", action="store_true")
    p_insights_generate.add_argument("--limit", type=int, default=20)
    p_insights_generate.add_argument("--json", action="store_true")
    p_insights_show = insights_sub.add_parser("show", help="Show one local draft insight note")
    p_insights_show.add_argument("insight_id")
    p_insights_show.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one capture")
    p_show.add_argument("capture_id")
    p_show.add_argument("--json", action="store_true")

    p_graph = sub.add_parser("graph", help="Export ontology-oriented local graph data")
    graph_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)
    p_graph_init = graph_sub.add_parser("init", help="Initialize the local semantic graph store")
    p_graph_init.add_argument("--path", type=Path)
    p_graph_init.add_argument("--json", action="store_true")
    p_graph_sync = graph_sub.add_parser("sync", help="Rebuild the semantic graph store from SQLite archive rows")
    p_graph_sync.add_argument("--path", type=Path)
    p_graph_sync.add_argument("--limit", type=int)
    p_graph_sync.add_argument("--include-raw-text", action="store_true")
    p_graph_sync.add_argument("--json", action="store_true")
    p_graph_store_export = graph_sub.add_parser("store-export", help="Dump the semantic graph store as N-Quads")
    p_graph_store_export.add_argument("--path", type=Path)
    p_graph_store_export.add_argument("--output", type=Path)
    p_graph_store_export.add_argument("--json", action="store_true")
    p_graph_export = graph_sub.add_parser("export", help="Export archive items as JSON-LD")
    p_graph_export.add_argument("--output", type=Path)
    p_graph_export.add_argument("--limit", type=int)
    p_graph_export.add_argument("--include-raw-text", action="store_true")
    p_graph_export.add_argument("--json", action="store_true")
    p_graph_stats = graph_sub.add_parser("stats", help="Show local semantic graph store stats")
    p_graph_stats.add_argument("--path", type=Path)
    p_graph_stats.add_argument("--json", action="store_true")
    p_graph_quality = graph_sub.add_parser("quality", help="Inspect archive readiness for graph and viewpoint work")
    p_graph_quality.add_argument("--limit", type=int, default=20)
    p_graph_quality.add_argument("--json", action="store_true")
    return parser

