from __future__ import annotations

import argparse
from pathlib import Path

from dalife.readiness import ISSUE_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dalife")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create local config, state directories, and SQLite schema")

    p_setup = sub.add_parser("setup", help="Configure .env and optionally install launchd")
    p_setup.add_argument("--dry-run", action="store_true")
    p_setup.add_argument("--non-interactive", action="store_true")
    p_setup.add_argument("--telegram-bot-token")
    p_setup.add_argument("--telegram-chat-id", "--telegram-allowed-chat-ids", dest="telegram_chat_id")
    p_setup.add_argument("--telegram-admin-user-id", "--telegram-admin-user-ids", dest="telegram_admin_user_id")
    p_setup.add_argument("--timezone")
    p_setup.add_argument("--allow-all-chats", action="store_true")
    p_setup.add_argument("--naver-client-id")
    p_setup.add_argument("--naver-client-secret")
    p_setup.add_argument("--kakao-rest-api-key")
    p_setup.add_argument("--codex-bin")
    p_setup.add_argument("--sync-telegram-commands", action="store_true")
    p_setup.add_argument("--install-launchd", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Check local config and optional Telegram connectivity")
    p_doctor.add_argument("--online", action="store_true", help="Also call Telegram getMe when a token is configured")

    p_discover = sub.add_parser("discover-chat", help="Find Telegram chat ids from recent bot updates")
    p_discover.add_argument("--plain", action="store_true")
    p_discover.add_argument("--json", action="store_true")

    sub.add_parser("rooms", help="Show registered Telegram dalife room status")

    p_commands = sub.add_parser("telegram-commands", help="Show or sync Telegram command menu")
    commands_sub = p_commands.add_subparsers(dest="telegram_commands_cmd", required=True)
    commands_sub.add_parser("show", help="Show current Telegram command menu")
    commands_sub.add_parser("sync", help="Sync Telegram command menu")

    sub.add_parser("setup-telegram-commands", help=argparse.SUPPRESS)

    p_send_test = sub.add_parser("send-test", help="Send a test message")
    p_send_test.add_argument("--chat-id")
    p_send_test.add_argument("--registered", action="store_true", help="Use the registered dalife room")
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

    p_archive = sub.add_parser("archive", help="Inspect and process local archive data")
    archive_sub = p_archive.add_subparsers(dest="archive_cmd", required=True)
    p_archive_pending = archive_sub.add_parser("pending", help="Preview pending captures and processor inputs")
    p_archive_pending.add_argument("--limit", type=int)
    p_archive_pending.add_argument("--no-codex", action="store_true")
    p_archive_pending.add_argument("--json", action="store_true")
    p_archive_process = archive_sub.add_parser("process", help="Process pending captures into archive metadata")
    p_archive_process.add_argument("--limit", type=int)
    p_archive_process.add_argument("--dry-run", action="store_true")
    p_archive_process.add_argument("--no-codex", action="store_true", help="Use the deterministic fallback processor")
    p_archive_process.add_argument(
        "--export-graph",
        action="store_true",
        help="Refresh the semantic graph store and JSON-LD export after processing",
    )
    p_archive_process.add_argument("--json", action="store_true")
    p_archive_list = archive_sub.add_parser("list", help="List recent captures")
    p_archive_list.add_argument("--limit", type=int, default=20)
    p_archive_list.add_argument("--interest", help="Only show archived captures matching an interest")
    p_archive_list.add_argument("--json", action="store_true")
    p_archive_search = archive_sub.add_parser("search", help="Search archived captures with the local SQLite FTS index")
    p_archive_search.add_argument("query")
    p_archive_search.add_argument("--limit", type=int, default=20)
    p_archive_search.add_argument("--rebuild", action="store_true", help="Rebuild the generated FTS index before searching")
    p_archive_search.add_argument("--json", action="store_true")
    p_archive_review = archive_sub.add_parser("review", help="List local archive items that need review or revisit")
    p_archive_review.add_argument("--limit", type=int, default=20)
    p_archive_review.add_argument("--needs-review", action="store_true")
    p_archive_review.add_argument("--revisit", action="store_true")
    p_archive_review.add_argument("--json", action="store_true")
    p_archive_show = archive_sub.add_parser("show", help="Show one capture")
    p_archive_show.add_argument("capture_id")
    p_archive_show.add_argument("--json", action="store_true")
    p_archive_interests = archive_sub.add_parser("interests", help="Inspect archive interest distribution")
    p_archive_interests.add_argument("--limit", type=int, default=20)
    p_archive_interests.add_argument("--json", action="store_true")
    p_archive_concepts = archive_sub.add_parser("concepts", help="Inspect archive concept/tag distribution")
    p_archive_concepts.add_argument("--limit", type=int, default=20)
    p_archive_concepts.add_argument("--json", action="store_true")
    p_archive_related = archive_sub.add_parser("related", help="Inspect read-only related captures from local graph signals")
    p_archive_related.add_argument("capture_id")
    p_archive_related.add_argument("--limit", type=int, default=10)
    p_archive_related.add_argument("--json", action="store_true")

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

    p_food = sub.add_parser("food", help="Plan and inspect local food recommendation data")
    food_sub = p_food.add_subparsers(dest="food_cmd", required=True)
    p_food_parse = food_sub.add_parser("parse", help="Parse a food recommendation request without provider calls")
    p_food_parse.add_argument("text")
    p_food_parse.add_argument("--default-count", type=int, default=30)
    p_food_parse.add_argument("--json", action="store_true")
    p_food_plan = food_sub.add_parser("plan-collection", help="Build a quota-aware food collection query plan")
    p_food_plan.add_argument("--area", required=True)
    p_food_plan.add_argument("--alias", action="append", default=[])
    p_food_plan.add_argument("--daily-quota-limit", type=int, default=30)
    p_food_plan.add_argument("--persist", action="store_true")
    p_food_plan.add_argument("--json", action="store_true")
    p_food_due = food_sub.add_parser("due-queries", help="List due food collection queries from the local ledger")
    p_food_due.add_argument("--due-at", default="")
    p_food_due.add_argument("--limit", type=int, default=20)
    p_food_due.add_argument("--json", action="store_true")
    p_food_run = food_sub.add_parser(
        "run-collection",
        help="Execute due food collection queries within provider quota budgets",
    )
    p_food_run.add_argument("--max-queries", type=int, default=20)
    p_food_run.add_argument("--max-quota-cost", type=int, default=20)
    p_food_run.add_argument("--dry-run", action="store_true")
    p_food_run.add_argument("--json", action="store_true")
    p_food_quota = food_sub.add_parser("quota", help="Show unified food provider quota usage")
    p_food_quota.add_argument("--json", action="store_true")
    p_food_config = food_sub.add_parser(
        "import-provider-config",
        help="Import Kakao/Naver provider settings from a Momukbot env file",
    )
    p_food_config.add_argument(
        "--source-env",
        type=Path,
        default=Path("/Users/hennei/workspace/momukbot/.env"),
    )
    p_food_config.add_argument("--overwrite", action="store_true")
    p_food_config.add_argument("--dry-run", action="store_true")
    p_food_config.add_argument("--json", action="store_true")
    p_food_history = food_sub.add_parser(
        "import-momuk-history",
        help="Import legacy Momuk recommendation history into shared SQLite",
    )
    p_food_history.add_argument(
        "--root",
        type=Path,
        default=Path("/Users/hennei/workspace/momukbot"),
    )
    p_food_history.add_argument("--dry-run", action="store_true")
    p_food_history.add_argument("--json", action="store_true")
    p_food_history_refresh = food_sub.add_parser(
        "plan-history-refresh",
        help="Plan exact-place refresh queries from selected legacy Momuk history",
    )
    p_food_history_refresh.add_argument("--area", required=True)
    p_food_history_refresh.add_argument("--legacy-area", action="append", default=[])
    p_food_history_refresh.add_argument("--place-limit", type=int, default=20)
    p_food_history_refresh.add_argument("--persist", action="store_true")
    p_food_history_refresh.add_argument("--json", action="store_true")
    p_food_recommend = food_sub.add_parser(
        "recommend-local",
        help="Rank recommendations from validated local SQLite food data",
    )
    p_food_recommend.add_argument("--area", required=True)
    p_food_recommend.add_argument("--topic", default="")
    p_food_recommend.add_argument("--occasion", default="")
    p_food_recommend.add_argument("--count", type=int, default=10)
    p_food_recommend.add_argument("--avoid", action="append", default=[])
    p_food_recommend.add_argument("--require", action="append", default=[])
    p_food_recommend.add_argument("--latitude", type=float)
    p_food_recommend.add_argument("--longitude", type=float)
    p_food_recommend.add_argument("--dry-run", action="store_true")
    p_food_recommend.add_argument("--json", action="store_true")

    p_life = sub.add_parser("life", help="Preview local life reminder behavior")
    life_sub = p_life.add_subparsers(dest="life_cmd", required=True)
    p_life_list = life_sub.add_parser("list", help="List imported default life reminder definitions")
    p_life_list.add_argument("--json", action="store_true")
    p_life_show = life_sub.add_parser("show", help="Show one SQLite-backed life reminder")
    p_life_show.add_argument("id")
    p_life_show.add_argument("--json", action="store_true")
    p_life_enable = life_sub.add_parser("enable", help="Enable one life reminder")
    p_life_enable.add_argument("id")
    p_life_disable = life_sub.add_parser("disable", help="Disable one life reminder")
    p_life_disable.add_argument("id")
    p_life_remove = life_sub.add_parser("remove", help="Remove one custom life reminder")
    p_life_remove.add_argument("id")
    p_life_add = life_sub.add_parser("add", help="Add a life reminder")
    life_add_sub = p_life_add.add_subparsers(dest="life_add_kind", required=True)
    p_life_add_custom = life_add_sub.add_parser("custom", help="Add a custom life reminder")
    p_life_add_custom.add_argument("--id", required=True)
    p_life_add_custom.add_argument("--title", required=True)
    p_life_add_custom.add_argument("--kind", required=True, choices=["one-off", "weekly", "interval"])
    p_life_add_custom.add_argument("--time", required=True)
    p_life_add_custom.add_argument("--action", required=True)
    p_life_add_custom.add_argument("--note", default="")
    p_life_add_custom.add_argument("--date")
    p_life_add_custom.add_argument("--weekday")
    p_life_add_custom.add_argument("--base-date")
    p_life_add_custom.add_argument("--days", type=int)
    p_life_update = life_sub.add_parser("update", help="Update one life reminder")
    p_life_update.add_argument("id")
    p_life_update.add_argument("--title")
    p_life_update.add_argument("--time")
    p_life_update.add_argument("--action")
    p_life_update.add_argument("--note")
    p_life_update.add_argument("--date")
    p_life_update.add_argument("--weekday")
    p_life_update.add_argument("--base-date")
    p_life_update.add_argument("--days", type=int)
    life_sub.add_parser("validate", help="Validate SQLite-backed reminder definitions")
    p_life_pending = life_sub.add_parser("pending", help="List pending life confirmations")
    p_life_pending.add_argument("--json", action="store_true")
    p_life_interactions = life_sub.add_parser("interactions", help="List life reminder responses")
    p_life_interactions.add_argument("--json", action="store_true")
    p_life_answer = life_sub.add_parser("answer", help="Manually answer a pending confirmation")
    p_life_answer.add_argument("confirmation_id")
    p_life_answer.add_argument("answer", choices=["yes", "no"])
    p_life_pattern = life_sub.add_parser("pattern", help="Manage life reminder message pattern")
    life_pattern_sub = p_life_pattern.add_subparsers(dest="life_pattern_cmd", required=True)
    life_pattern_sub.add_parser("show")
    p_life_pattern_set = life_pattern_sub.add_parser("set")
    p_life_pattern_set.add_argument("--prefix")
    p_life_pattern_set.add_argument("--schedule-label")
    p_life_pattern_set.add_argument("--action-label")
    p_life_pattern_set.add_argument("--note-label")
    p_life_preview = life_sub.add_parser("preview", help="Preview life reminders due at a specific KST time")
    p_life_preview.add_argument("--date", required=True)
    p_life_preview.add_argument("--time", required=True)
    p_life_preview.add_argument("--json", action="store_true")
    p_life_next = life_sub.add_parser("next", help="List upcoming life reminders from the default schedule")
    p_life_next.add_argument("--date", required=True)
    p_life_next.add_argument("--time", default="00:00")
    p_life_next.add_argument("--days", type=int, default=7)
    p_life_next.add_argument("--json", action="store_true")
    p_life_run = life_sub.add_parser("run-once", help="Send due SQLite-backed life reminders once")
    p_life_run.add_argument("--date", default="")
    p_life_run.add_argument("--time", default="")
    p_life_run.add_argument("--dry-run", action="store_true")
    p_life_run.add_argument("--json", action="store_true")
    p_life_import = life_sub.add_parser(
        "import-honsanam",
        help="Import Honsanam reminder config and state into local SQLite",
    )
    p_life_import.add_argument(
        "--root",
        type=Path,
        default=Path("/Users/hennei/workspace/honsanam-reminder-bot"),
    )
    p_life_import.add_argument("--dry-run", action="store_true")
    p_life_import.add_argument("--json", action="store_true")

    p_course = sub.add_parser("course", help="Plan personal courses from local context")
    course_sub = p_course.add_subparsers(dest="course_cmd", required=True)
    p_course_plan = course_sub.add_parser("plan", help="Create a local course plan draft")
    p_course_plan.add_argument("--title", default="Personal course")
    p_course_plan.add_argument("--area", required=True)
    p_course_plan.add_argument("--date", required=True)
    p_course_plan.add_argument("--time", required=True)
    p_course_plan.add_argument("--persist", action="store_true")
    p_course_plan.add_argument("--json", action="store_true")

    p_schedule = sub.add_parser("schedule", help="Inspect unified local scheduler plan")
    schedule_sub = p_schedule.add_subparsers(dest="schedule_cmd", required=True)
    p_schedule_plan = schedule_sub.add_parser("plan", help="Show planned unified scheduled jobs")
    p_schedule_plan.add_argument("--include-disabled", action="store_true")
    p_schedule_plan.add_argument("--json", action="store_true")
    p_schedule_cutover = schedule_sub.add_parser(
        "cutover-check",
        help="Read-only audit for migrating legacy life reminder agents",
    )
    p_schedule_cutover.add_argument("--json", action="store_true")

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
