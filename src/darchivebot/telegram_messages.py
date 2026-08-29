from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        candidates = [item for item in photos if isinstance(item, dict)]
        if candidates:
            selected = max(candidates, key=lambda item: int(item.get("file_size") or 0))
            attachments.append(
                {
                    "kind": "photo",
                    "file_id": str(selected.get("file_id") or ""),
                    "file_unique_id": str(selected.get("file_unique_id") or ""),
                    "file_size": int(selected.get("file_size") or 0),
                    "mime_type": "image/jpeg",
                    "file_name": "photo.jpg",
                }
            )
    document = message.get("document")
    if isinstance(document, dict):
        attachments.append(
            {
                "kind": "document",
                "file_id": str(document.get("file_id") or ""),
                "file_unique_id": str(document.get("file_unique_id") or ""),
                "file_size": int(document.get("file_size") or 0),
                "mime_type": str(document.get("mime_type") or ""),
                "file_name": str(document.get("file_name") or "document"),
            }
        )
    return [item for item in attachments if item["file_id"]]


SERVICE_MESSAGE_KEYS = {
    "new_chat_member",
    "new_chat_members",
    "new_chat_participant",
    "left_chat_member",
    "left_chat_participant",
    "pinned_message",
    "group_chat_created",
    "supergroup_chat_created",
    "channel_chat_created",
    "message_auto_delete_timer_changed",
    "migrate_to_chat_id",
    "migrate_from_chat_id",
    "forum_topic_created",
    "forum_topic_edited",
    "forum_topic_closed",
    "forum_topic_reopened",
    "video_chat_scheduled",
    "video_chat_started",
    "video_chat_ended",
    "video_chat_participants_invited",
}

def is_capturable_message(message: dict[str, Any]) -> bool:
    if any(key in message for key in SERVICE_MESSAGE_KEYS):
        return False
    text = str(message.get("text") or "").strip()
    caption = str(message.get("caption") or "").strip()
    return bool(text or caption or extract_attachments(message))

def content_kind_for_message(text: str, caption: str, attachments: list[dict[str, Any]]) -> str:
    kinds = {item["kind"] for item in attachments}
    if "photo" in kinds:
        return "screenshot" if caption_or_text_mentions_screenshot(text, caption) else "photo"
    if "document" in kinds:
        return "document"
    return "text"

def caption_or_text_mentions_screenshot(text: str, caption: str) -> bool:
    haystack = f"{text} {caption}".lower()
    return any(token in haystack for token in ("screenshot", "screen shot", "capture", "캡처", "스크린샷"))

def parse_command(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ""
    return stripped.split(maxsplit=1)[0].split("@", 1)[0]

def command_argument(text: str) -> str:
    stripped = text.strip()
    parts = stripped.split(maxsplit=1)
    return parts[1].strip().lower() if len(parts) > 1 else ""

def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def chat_display_name(chat: dict[str, Any]) -> str:
    return str(chat.get("title") or chat.get("username") or chat.get("first_name") or chat.get("type") or chat.get("id") or "")

def user_display_name(user: dict[str, Any]) -> str:
    parts = [str(user.get("first_name") or ""), str(user.get("last_name") or "")]
    name = " ".join(part for part in parts if part).strip()
    return name or str(user.get("username") or user.get("id") or "")

def safe_file_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in value)
    return cleaned[:180] or "file"
