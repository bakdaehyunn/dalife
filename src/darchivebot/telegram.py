from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from darchivebot.config import Settings
from darchivebot.domains.life import apply_life_callback, parse_life_callback_data
from darchivebot.json_utils import dumps
from darchivebot.ports import TelegramStore
from darchivebot.telegram_api import TelegramApiClient
from darchivebot.telegram_intents import TelegramIntent, classify_telegram_update
from darchivebot.telegram_food import (
    apply_food_feedback_callback,
    parse_food_feedback_callback,
    recommend_food_for_telegram,
)
from darchivebot.telegram_course import plan_course_for_telegram
from darchivebot.telegram_life import upcoming_life_for_telegram
from darchivebot.telegram_messages import (
    caption_or_text_mentions_screenshot,
    chat_display_name,
    command_argument,
    content_kind_for_message,
    extract_attachments,
    is_capturable_message,
    object_value,
    parse_command,
    safe_file_name,
    user_display_name,
)
from darchivebot.telegram_prompts import (
    choice_label,
    format_prompt_message,
    inline_keyboard_for_prompt,
    parse_prompt_callback_data,
    prompt_callback_data,
    prompt_choices,
    send_bot_prompt,
)
from darchivebot.telegram_rooms import (
    DEFAULT_BOT_COMMANDS,
    REGISTERED_CHAT_BOT_COMMANDS,
    REGISTER_CHAT_ROOM_COMMAND,
    TelegramChatCandidate,
    TelegramRoomState,
    allowed_chat_ids,
    chat_command_scope,
    command_menu_is_synced,
    discover_chat_candidates,
    format_rooms_report,
    mask_identifier,
    read_registered_chat_id,
    read_room_state,
)


class TelegramCaptureBot:
    def __init__(
        self,
        settings: Settings,
        store: TelegramStore,
        api: TelegramApiClient | None = None,
    ) -> None:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        self.settings = settings
        self.store = store
        self.api = api or TelegramApiClient(settings.telegram_bot_token)
        self.logger = build_logger(settings)

    def run_polling(self, poll_interval_sec: float = 1.0) -> None:
        offset: int | None = None
        while True:
            try:
                updates = self.get_updates(offset=offset, timeout=30)
                for update in updates:
                    offset = max(offset or 0, int(update.get("update_id", 0)) + 1)
                    self.handle_update(update)
            except Exception:
                self.logger.exception("telegram polling failed")
                time.sleep(max(1.0, poll_interval_sec))
            time.sleep(poll_interval_sec)

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict[str, Any]]:
        payload = self.api.get_updates(offset=offset, timeout=timeout, limit=None)
        result = payload.get("result")
        return result if isinstance(result, list) else []

    def handle_update(self, update: dict[str, Any]) -> str | None:
        intent = classify_telegram_update(update)
        callback_query = update.get("callback_query")
        if isinstance(callback_query, dict):
            self.handle_callback_query(callback_query)
            return None
        message = update.get("message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat")
        if not isinstance(chat, dict):
            return None
        chat_id = str(chat.get("id") or "")
        text = str(message.get("text") or "")
        command = parse_command(text)
        if command in {"/chatid", REGISTER_CHAT_ROOM_COMMAND}:
            self.handle_admin_command(command, chat_id, chat, message, text)
            return None
        if command:
            return None
        if not self.is_allowed(chat_id):
            return None
        if (
            self.settings.native_personal_telegram_enabled
            and intent.intent == TelegramIntent.FOOD_RECOMMENDATION
        ):
            self.handle_food_recommendation(chat_id, text)
            return None
        if (
            self.settings.native_personal_telegram_enabled
            and intent.intent == TelegramIntent.COURSE_PLANNING
        ):
            self.handle_course_planning(chat_id, text)
            return None
        if (
            self.settings.native_personal_telegram_enabled
            and intent.intent == TelegramIntent.LIFE_REMINDER
        ):
            self.handle_life_query(chat_id, text)
            return None
        if intent.intent == TelegramIntent.IGNORE or not is_capturable_message(message):
            return None
        return self.capture_message(message)

    def handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        callback_id = str(callback_query.get("id") or "")
        data = str(callback_query.get("data") or "")
        message = object_value(callback_query.get("message"))
        chat = object_value(message.get("chat"))
        chat_id = str(chat.get("id") or "")
        user = object_value(callback_query.get("from"))
        user_id = str(user.get("id") or "")
        if parse_food_feedback_callback(data):
            self.handle_food_feedback_callback(
                callback_id=callback_id,
                data=data,
                chat_id=chat_id,
                user_id=user_id,
            )
            return
        if parse_life_callback_data(data):
            self.handle_life_callback(
                callback_id=callback_id,
                data=data,
                chat_id=chat_id,
                user_id=user_id,
                message=message,
            )
            return
        parsed = parse_prompt_callback_data(data)
        if not parsed:
            self.answer_callback(callback_id, "Unknown choice")
            return
        prompt_id, choice = parsed
        prompt = self.store.get_bot_prompt(prompt_id)
        if prompt is None:
            self.answer_callback(callback_id, "Prompt not found")
            return
        if chat_id and str(prompt["chat_id"]) != chat_id:
            self.answer_callback(callback_id, "This prompt belongs to another chat")
            return
        if chat_id and not self.is_allowed(chat_id):
            self.answer_callback(callback_id, "Chat is not allowed")
            return
        choices = prompt_choices(prompt)
        if choice not in {item["choice"] for item in choices}:
            self.answer_callback(callback_id, "Choice is not available")
            return
        row = self.store.record_bot_prompt_choice(
            prompt_id,
            choice=choice,
            actor_user_id=user_id,
            payload={"callback_query_id": callback_id, "chat_id": chat_id},
        )
        label = choice_label(choices, choice)
        self.answer_callback(callback_id, f"Saved: {label}")
        if row is not None:
            self.logger.info("bot prompt choice prompt_id=%s choice=%s user_id=%s", prompt_id, choice, user_id)

    def handle_food_recommendation(self, chat_id: str, text: str) -> None:
        result = recommend_food_for_telegram(self.store, text)
        for message in result.messages:
            self.api.send_message(chat_id, message.text, reply_markup=message.reply_markup)
        self.logger.info(
            "food recommendation chat_id=%s session_id=%s returned=%s",
            chat_id,
            result.session_id,
            result.returned_count,
        )

    def handle_course_planning(self, chat_id: str, text: str) -> None:
        response = plan_course_for_telegram(
            self.store,
            text,
            now=datetime.now(ZoneInfo(self.settings.life_timezone)),
        )
        self.api.send_message(chat_id, response)
        self.logger.info("course plan chat_id=%s", chat_id)

    def handle_life_query(self, chat_id: str, text: str) -> None:
        response = upcoming_life_for_telegram(
            self.store,
            text,
            now=datetime.now(ZoneInfo(self.settings.life_timezone)),
        )
        self.api.send_message(chat_id, response)
        self.logger.info("life query chat_id=%s", chat_id)

    def handle_food_feedback_callback(
        self,
        *,
        callback_id: str,
        data: str,
        chat_id: str,
        user_id: str,
    ) -> None:
        if not self.settings.native_personal_telegram_enabled:
            self.answer_callback(callback_id, "Food feedback is not enabled")
            return
        if chat_id and not self.is_allowed(chat_id):
            self.answer_callback(callback_id, "Chat is not allowed")
            return
        answer = apply_food_feedback_callback(
            self.store,
            data,
            callback_query_id=callback_id,
        )
        if answer is None:
            self.answer_callback(callback_id, "Recommendation not found")
            return
        self.answer_callback(callback_id, answer)
        self.logger.info("food feedback callback=%s user_id=%s", data, user_id)

    def handle_life_callback(
        self,
        *,
        callback_id: str,
        data: str,
        chat_id: str,
        user_id: str,
        message: dict[str, Any],
    ) -> None:
        if chat_id and not self.is_allowed(chat_id):
            self.answer_callback(callback_id, "Chat is not allowed")
            return
        result = apply_life_callback(
            self.store,
            data,
            responded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            callback_query_id=callback_id,
            chat_id=chat_id,
            user_id=user_id,
        )
        if result is None:
            self.answer_callback(callback_id, "Reminder action not found")
            return
        self.answer_callback(callback_id, result.answer_text)
        message_id = message.get("message_id")
        if chat_id and isinstance(message_id, int):
            try:
                self.api.edit_message_reply_markup(chat_id, message_id)
            except Exception:
                self.logger.exception("failed to clear life reminder keyboard")
        self.logger.info(
            "life reminder response event_id=%s action=%s user_id=%s",
            result.event["id"],
            result.action,
            user_id,
        )

    def answer_callback(self, callback_id: str, text: str) -> None:
        if not callback_id:
            return
        try:
            self.api.answer_callback_query(callback_id, text)
        except Exception:
            self.logger.exception("failed to answer Telegram callback query")

    def capture_message(self, message: dict[str, Any]) -> str:
        chat = object_value(message.get("chat"))
        user = object_value(message.get("from"))
        chat_id = str(chat.get("id") or "")
        message_id = int(message.get("message_id") or 0)
        text = str(message.get("text") or "")
        caption = str(message.get("caption") or "")
        attachments = extract_attachments(message)
        content_kind = content_kind_for_message(text, caption, attachments)
        capture_id = self.store.add_capture(
            capture_key=f"{chat_id}:{message_id}",
            chat_id=chat_id,
            message_id=message_id,
            chat_type=str(chat.get("type") or ""),
            chat_title=chat_display_name(chat),
            sender_user_id=str(user.get("id") or ""),
            sender_name=user_display_name(user),
            message_date=int(message["date"]) if isinstance(message.get("date"), int) else None,
            text=text,
            caption=caption,
            content_kind=content_kind,
            raw_message=message,
        )
        for attachment in attachments:
            local_path, status = self.download_attachment(capture_id, message, attachment)
            self.store.add_file(
                capture_id=capture_id,
                telegram_file_id=attachment["file_id"],
                telegram_file_unique_id=attachment.get("file_unique_id", ""),
                file_kind=attachment["kind"],
                mime_type=attachment.get("mime_type", ""),
                file_name=attachment.get("file_name", ""),
                file_size=attachment.get("file_size"),
                local_path=str(local_path) if local_path else "",
                download_status=status,
            )
        return capture_id

    def download_attachment(
        self,
        capture_id: str,
        message: dict[str, Any],
        attachment: dict[str, Any],
    ) -> tuple[Path | None, str]:
        try:
            file_payload = self.api.get_file(attachment["file_id"])
            file_path = str(file_payload.get("file_path") or "")
            if not file_path:
                return None, "missing_file_path"
            destination = self.local_media_path(capture_id, message, attachment, file_path)
            self.api.download_file(file_path, destination)
            return destination, "downloaded"
        except Exception:
            self.logger.exception("failed to download Telegram file capture_id=%s", capture_id)
            return None, "failed"

    def local_media_path(
        self,
        capture_id: str,
        message: dict[str, Any],
        attachment: dict[str, Any],
        telegram_file_path: str,
    ) -> Path:
        timestamp = datetime.fromtimestamp(int(message.get("date") or time.time()))
        folder = self.settings.media_dir / timestamp.strftime("%Y") / timestamp.strftime("%m") / timestamp.strftime("%d")
        raw_name = attachment.get("file_name") or Path(telegram_file_path).name or f"{capture_id}.bin"
        file_name = safe_file_name(raw_name)
        return folder / f"{capture_id}-{attachment['kind']}-{file_name}"

    def handle_admin_command(
        self,
        command: str,
        chat_id: str,
        chat: dict[str, Any],
        message: dict[str, Any],
        text: str,
    ) -> None:
        if not self.is_admin_message(message):
            return
        if command == "/chatid":
            self.api.send_message(chat_id, f"chat_id: {chat_id}\ntype: {chat.get('type') or ''}\ntitle: {chat_display_name(chat)}")
            return
        if command == REGISTER_CHAT_ROOM_COMMAND:
            if not self.can_overwrite_registered_room(chat_id, chat, text):
                return
            self.save_registered_room(chat_id, chat, message)
            self.api.send_message(chat_id, f"DaLife 사용 방으로 등록했습니다.\nchat_id: {chat_id}")
            self.sync_registered_chat_commands(chat_id)

    def can_overwrite_registered_room(self, chat_id: str, chat: dict[str, Any], text: str) -> bool:
        state = read_room_state(self.settings)
        if not state.darchive_chat_id or state.darchive_chat_id == chat_id:
            return True
        if command_argument(text) == "confirm":
            return True
        self.api.send_message(
            chat_id,
            (
                "이미 다른 방이 DaLife 사용 방으로 등록되어 있습니다.\n"
                f"기존: {state.darchive_chat_id} / {state.darchive_chat_title or '(empty)'}\n"
                f"새 방: {chat_id} / {chat_display_name(chat) or '(empty)'}\n"
                f"정말 바꾸려면 {REGISTER_CHAT_ROOM_COMMAND} confirm 을 보내주세요."
            ),
        )
        return False

    def sync_registered_chat_commands(self, chat_id: str) -> None:
        try:
            self.api.set_my_commands(REGISTERED_CHAT_BOT_COMMANDS, scope=chat_command_scope(chat_id))
        except Exception:
            self.logger.exception("failed to sync registered chat Telegram commands")

    def save_registered_room(self, chat_id: str, chat: dict[str, Any], message: dict[str, Any]) -> None:
        self.settings.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.state_dir / "telegram_rooms.json"
        user = object_value(message.get("from"))
        data = {
            "darchive_chat_id": chat_id,
            "darchive_chat_title": chat_display_name(chat),
            "darchive_chat_type": str(chat.get("type") or ""),
            "registered_by_user_id": str(user.get("id") or ""),
            "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    def is_admin_message(self, message: dict[str, Any]) -> bool:
        allowed = self.settings.telegram_admin_user_ids
        if not allowed:
            return False
        user = message.get("from")
        if not isinstance(user, dict):
            return False
        return str(user.get("id") or "") in allowed

    def is_allowed(self, chat_id: str) -> bool:
        allowed = allowed_chat_ids(self.settings)
        if allowed:
            return chat_id in allowed
        return self.settings.telegram_allow_all_chats


def build_logger(settings: Settings) -> logging.Logger:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("darchivebot.telegram")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(settings.log_dir / "telegram.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
