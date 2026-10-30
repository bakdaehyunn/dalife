from __future__ import annotations

from typing import Any

from dalife.config import Settings


def only_allowed_chat_id(settings: Settings) -> str:
    if len(settings.telegram_allowed_chat_ids) == 1:
        return settings.telegram_allowed_chat_ids[0]
    return ""

def mask_identifier(value: str) -> str:
    raw = str(value or "")
    if len(raw) <= 4:
        return "***"
    return f"***{raw[-4:]}"

def format_file_status(row: Any) -> str:
    file_count = int(row["file_count"] or 0)
    if file_count == 0:
        return "none"
    statuses = str(row["file_download_statuses"] or "").replace(",", "+") or "unknown"
    return f"{file_count}:{statuses}"

def format_classification_preview(primary_interest: str, topic: str) -> str:
    parts = []
    if primary_interest:
        parts.append(f"interest={primary_interest}")
    if topic:
        parts.append(f"topic={topic}")
    return "\t" + " ".join(parts) if parts else ""

def format_search_label(item: dict[str, Any]) -> str:
    parts = []
    if item.get("primary_interest"):
        parts.append(f"interest={item['primary_interest']}")
    if item.get("topic"):
        parts.append(f"topic={item['topic']}")
    if item.get("needs_review"):
        parts.append("needs_review")
    if item.get("revisit_priority"):
        parts.append(f"revisit={item['revisit_priority']}")
    return " ".join(parts) if parts else "archived"

def print_process_progress(event: dict[str, Any]) -> None:
    name = event.get("event")
    capture_id = event.get("capture_id", "-")
    processor = event.get("processor", "-")
    kind = event.get("content_kind", "-")
    if name == "start":
        print(f"[process:start] capture={capture_id} kind={kind} processor={processor}")
    elif name == "finish":
        print(
            f"[process:done] capture={capture_id} kind={kind} "
            f"processor={processor} elapsed={event.get('elapsed_sec')}s"
        )
    elif name == "failed":
        print(
            f"[process:failed] capture={capture_id} kind={kind} processor={processor} "
            f"elapsed={event.get('elapsed_sec')}s error={event.get('error')}"
        )
    elif name == "skipped":
        print(
            f"[process:skip] capture={capture_id} kind={kind} "
            f"reason={event.get('reason', '-')}"
        )
