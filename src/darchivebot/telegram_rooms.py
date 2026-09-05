from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from darchivebot.config import Settings
from darchivebot.telegram_messages import chat_display_name, object_value


DEFAULT_BOT_COMMANDS = [
    {"command": "chatid", "description": "설정용 채팅방 ID 확인"},
]
REGISTERED_CHAT_BOT_COMMANDS = [
    *DEFAULT_BOT_COMMANDS,
    {"command": "set_chat_room", "description": "DaLife 사용 방 등록"},
]
REGISTER_CHAT_ROOM_COMMAND = "/set_chat_room"


@dataclass(frozen=True)
class TelegramChatCandidate:
    chat_id: str
    title: str
    chat_type: str


@dataclass(frozen=True)
class TelegramRoomState:
    darchive_chat_id: str = ""
    darchive_chat_title: str = ""
    darchive_chat_type: str = ""
    registered_by_user_id: str = ""
    registered_at: str = ""
    unreadable_error: str = ""


def read_room_state(settings: Settings) -> TelegramRoomState:
    path = settings.state_dir / "telegram_rooms.json"
    if not path.exists():
        return TelegramRoomState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return TelegramRoomState(unreadable_error=str(exc))
    if not isinstance(payload, dict):
        return TelegramRoomState(unreadable_error="telegram room state is not a JSON object")
    return TelegramRoomState(
        darchive_chat_id=str(payload.get("darchive_chat_id") or "").strip(),
        darchive_chat_title=str(payload.get("darchive_chat_title") or "").strip(),
        darchive_chat_type=str(payload.get("darchive_chat_type") or "").strip(),
        registered_by_user_id=str(payload.get("registered_by_user_id") or "").strip(),
        registered_at=str(payload.get("registered_at") or "").strip(),
    )

def read_registered_chat_id(settings: Settings) -> str:
    return read_room_state(settings).darchive_chat_id

def allowed_chat_ids(settings: Settings) -> set[str]:
    allowed = set(settings.telegram_allowed_chat_ids)
    registered = read_registered_chat_id(settings)
    if registered:
        allowed.add(registered)
    return allowed

def chat_command_scope(chat_id: str) -> dict[str, str]:
    return {"type": "chat", "chat_id": chat_id}

def command_menu_is_synced(commands: list[dict[str, str]], expected: list[dict[str, str]]) -> bool:
    normalized = [
        {
            "command": str(item.get("command") or ""),
            "description": str(item.get("description") or ""),
        }
        for item in commands
    ]
    return normalized == expected

def format_rooms_report(settings: Settings) -> tuple[int, str]:
    state = read_room_state(settings)
    if state.unreadable_error:
        return 1, f"[FAIL] telegram room state is unreadable: {state.unreadable_error}"
    lines: list[str] = []
    if state.darchive_chat_id:
        lines.extend(
            [
                f"darchive_chat_id={mask_identifier(state.darchive_chat_id)}",
                f"title={state.darchive_chat_title or '(empty)'}",
                f"type={state.darchive_chat_type or '(empty)'}",
                f"registered_by_user_id={mask_identifier(state.registered_by_user_id) if state.registered_by_user_id else '(empty)'}",
                f"registered_at={state.registered_at or '(empty)'}",
                f"allowed={'yes' if state.darchive_chat_id in allowed_chat_ids(settings) else 'no'}",
            ]
        )
    else:
        lines.append(f"[WARN] darchive_chat_id is not registered; send {REGISTER_CHAT_ROOM_COMMAND} in the Telegram chat")
    if settings.telegram_allowed_chat_ids:
        lines.append(f"env_allowed_chat_ids={','.join(mask_identifier(item) for item in settings.telegram_allowed_chat_ids)}")
    elif settings.telegram_allow_all_chats:
        lines.append("[WARN] DARCHIVE_ALLOW_ALL_CHATS=true; every chat can use the bot")
    else:
        lines.append("env_allowed_chat_ids=(empty)")
    return 0, "\n".join(lines)

def mask_identifier(value: str) -> str:
    raw = str(value or "")
    if len(raw) <= 4:
        return "***"
    return f"***{raw[-4:]}"

def discover_chat_candidates(payload: dict[str, Any]) -> list[TelegramChatCandidate]:
    result = payload.get("result", [])
    if not isinstance(result, list):
        return []
    candidates: list[TelegramChatCandidate] = []
    seen: set[str] = set()
    for update in result:
        if not isinstance(update, dict):
            continue
        for key in ("message", "edited_message", "channel_post", "edited_channel_post", "my_chat_member", "chat_member"):
            event = update.get(key)
            if not isinstance(event, dict):
                continue
            chat = event.get("chat")
            if not isinstance(chat, dict):
                continue
            raw_chat_id = chat.get("id")
            if raw_chat_id is None:
                continue
            chat_id = str(raw_chat_id)
            if chat_id in seen:
                continue
            seen.add(chat_id)
            candidates.append(
                TelegramChatCandidate(
                    chat_id=chat_id,
                    title=chat_display_name(chat),
                    chat_type=str(chat.get("type") or ""),
                )
            )
    return candidates
