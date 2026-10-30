from __future__ import annotations

from typing import Any

from dalife.archive_values import json_array
from dalife.models import ArchiveItemRecord, BotPromptRecord
from dalife.ports import PromptStore


POST_PROCESS_CHOICES = [
    {"choice": "project_seed", "label": "Project seed"},
    {"choice": "revisit", "label": "Revisit"},
    {"choice": "keep", "label": "Keep"},
    {"choice": "needs_review", "label": "Needs review"},
    {"choice": "ignore", "label": "Ignore"},
]


def create_post_process_prompt(store: PromptStore, capture_id: str) -> dict[str, Any] | None:
    capture = store.get_capture(capture_id)
    archive = store.get_archive_item(capture_id)
    if capture is None or archive is None:
        return None
    chat_id = str(capture["chat_id"] or "").strip()
    if not chat_id:
        return None
    classification = prompt_classification(archive)
    if classification == "none":
        return None
    prompt = store.create_bot_prompt(
        prompt_key=f"capture:{capture_id}:post-process:v1",
        chat_id=chat_id,
        prompt_type=classification,
        capture_id=capture_id,
        archive_item_id=str(archive["id"]),
        title=safe_title(archive),
        body=post_process_body(archive, classification),
        recommended_action=recommended_action_for_classification(classification),
        choices=POST_PROCESS_CHOICES,
    )
    return prompt_to_dict(prompt)

def prompt_classification(row: ArchiveItemRecord) -> str:
    if bool(row["needs_review"]) or float(row["confidence"] or 0.0) < 0.5:
        return "review_classification"
    primary = str(row["primary_interest"] or "").strip().lower()
    topic = str(row["topic"] or "").strip()
    if not primary or primary == "other/unknown" or not topic:
        return "review_classification"
    if str(row["insight_seed"] or "").strip():
        return "project_seed_candidate"
    if str(row["revisit_reason"] or "").strip() or str(row["revisit_priority"] or "").strip().lower() in {"urgent", "high"}:
        return "revisit_candidate"
    return "none"


def recommended_action_for_classification(classification: str) -> str:
    return {
        "review_classification": "Please classify or mark this for review.",
        "project_seed_candidate": "This looks like a project seed candidate.",
        "revisit_candidate": "This looks worth revisiting.",
    }.get(classification, "Choose how to keep this archive item.")


def post_process_body(row: ArchiveItemRecord, classification: str) -> str:
    lines = [
        f"Title: {safe_title(row)}",
        f"Summary: {safe_summary(row)}",
    ]
    meta = " / ".join(part for part in [row["primary_interest"], row["topic"]] if str(part or "").strip())
    if meta:
        lines.append(f"Suggested class: {meta}")
    if str(row["revisit_reason"] or "").strip():
        lines.append(f"Why revisit: {truncate(row['revisit_reason'], 180)}")
    if str(row["insight_seed"] or "").strip():
        lines.append(f"Seed: {truncate(row['insight_seed'], 180)}")
    lines.append(recommended_action_for_classification(classification))
    return "\n".join(lines)


def prompt_to_dict(row: BotPromptRecord) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "prompt_key": str(row["prompt_key"]),
        "chat_id": str(row["chat_id"]),
        "prompt_type": str(row["prompt_type"]),
        "status": str(row["status"]),
        "title": str(row["title"]),
        "body": str(row["body"]),
        "recommended_action": str(row["recommended_action"]),
        "choices": decode_choices(row["choices_json"]),
    }


def safe_title(row: ArchiveItemRecord) -> str:
    return truncate(row["title"] or "Untitled archive item", 120)


def safe_summary(row: ArchiveItemRecord) -> str:
    return truncate(row["core_summary"] or row["summary"] or "", 260)


def truncate(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def decode_choices(value: Any) -> list[dict[str, str]]:
    payload = json_array(value)
    return [
        {"choice": str(item.get("choice") or ""), "label": str(item.get("label") or "")}
        for item in payload
        if isinstance(item, dict) and str(item.get("choice") or "").strip()
    ]
