from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dalife.archive_values import json_array
from dalife.insights import generate_insight_note
from dalife.models import ArchiveItemRecord, BotPromptRecord
from dalife.ports import PromptStore


POST_PROCESS_CHOICES = [
    {"choice": "project_seed", "label": "Project seed"},
    {"choice": "revisit", "label": "Revisit"},
    {"choice": "keep", "label": "Keep"},
    {"choice": "needs_review", "label": "Needs review"},
    {"choice": "ignore", "label": "Ignore"},
]
DIGEST_CHOICES = [
    {"choice": "open_project_seed", "label": "Project seed"},
    {"choice": "revisit", "label": "Revisit"},
    {"choice": "keep", "label": "Keep"},
    {"choice": "ignore", "label": "Ignore"},
]
WEEKLY_CHOICES = [
    {"choice": "create_weekly_insight", "label": "Create insight"},
    {"choice": "later", "label": "Later"},
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


def create_revisit_digest_prompt(store: PromptStore, chat_id: str, *, limit: int = 3) -> dict[str, Any] | None:
    rows = store.review_archive_items(limit=limit, revisit_only=True)
    if not rows:
        return None
    today = datetime.now(timezone.utc).date().isoformat()
    body = "\n\n".join(digest_item_line(index, row) for index, row in enumerate(rows, start=1))
    prompt = store.create_bot_prompt(
        prompt_key=f"digest:revisit:{chat_id}:{today}:v1",
        chat_id=chat_id,
        prompt_type="digest_revisit",
        title="Today's archive revisit candidates",
        body=body,
        recommended_action="Pick anything worth turning into a project seed or revisit item.",
        choices=DIGEST_CHOICES,
    )
    return prompt_to_dict(prompt)


def create_project_seed_digest_prompt(store: PromptStore, chat_id: str, *, limit: int = 3) -> dict[str, Any] | None:
    rows = [
        row
        for row in store.review_archive_items(limit=20, revisit_only=True)
        if str(row["insight_seed"] or "").strip()
    ][:limit]
    if not rows:
        return None
    today = datetime.now(timezone.utc).date().isoformat()
    body = "\n\n".join(project_seed_digest_item_line(index, row) for index, row in enumerate(rows, start=1))
    prompt = store.create_bot_prompt(
        prompt_key=f"digest:project-seed:{chat_id}:{today}:v1",
        chat_id=chat_id,
        prompt_type="digest_project_seed",
        title="Project seed candidates from your archive",
        body=body,
        recommended_action="Choose whether any of these should become a project seed.",
        choices=DIGEST_CHOICES,
    )
    return prompt_to_dict(prompt)


def create_weekly_insight_prompt(store: PromptStore, chat_id: str) -> dict[str, Any] | None:
    result = generate_insight_note(store, period="weekly", dry_run=True, include_needs_review=False)
    if result.get("status") != "dry-run":
        return None
    note = result["would_create"]
    week = str(note.get("period_start") or "")[:10]
    prompt = store.create_bot_prompt(
        prompt_key=f"digest:weekly:{chat_id}:{week}:v1",
        chat_id=chat_id,
        prompt_type="digest_weekly_insight",
        title=str(note.get("title") or "Weekly insight draft"),
        body=str(note.get("summary") or "")[:700],
        recommended_action="Create a local weekly insight draft from this pattern?",
        choices=WEEKLY_CHOICES,
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


def digest_item_line(index: int, row: ArchiveItemRecord) -> str:
    parts = [
        f"{index}. {safe_title(row)}",
        truncate(row["core_summary"] or row["summary"], 160),
    ]
    reason = str(row["revisit_reason"] or row["insight_seed"] or "").strip()
    if reason:
        parts.append(f"Reason: {truncate(reason, 140)}")
    return "\n".join(part for part in parts if part)


def project_seed_digest_item_line(index: int, row: ArchiveItemRecord) -> str:
    parts = [
        f"{index}. {safe_title(row)}",
        truncate(row["core_summary"] or row["summary"], 160),
    ]
    seed = str(row["insight_seed"] or "").strip()
    if seed:
        parts.append(f"Seed: {truncate(seed, 160)}")
    reason = str(row["revisit_reason"] or "").strip()
    if reason:
        parts.append(f"Why revisit: {truncate(reason, 120)}")
    return "\n".join(part for part in parts if part)


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
