from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from darchivebot.telegram_messages import is_capturable_message, parse_command


class TelegramIntent(StrEnum):
    ADMIN_COMMAND = "admin_command"
    ARCHIVE_CAPTURE = "archive_capture"
    FOOD_RECOMMENDATION = "food_recommendation"
    LIFE_REMINDER = "life_reminder"
    COURSE_PLANNING = "course_planning"
    FEEDBACK_CALLBACK = "feedback_callback"
    IGNORE = "ignore"


@dataclass(frozen=True)
class TelegramIntentDecision:
    intent: TelegramIntent
    text: str = ""
    command: str = ""
    reason: str = ""


FOOD_TERMS = (
    "맛집",
    "뭐먹",
    "뭐 먹",
    "밥",
    "점심",
    "저녁",
    "술집",
    "카페",
    "브런치",
)
LIFE_TERMS = (
    "알림",
    "리마인더",
    "청소",
    "분리수거",
    "미용실",
    "손톱",
    "발톱",
    "칫솔",
)
COURSE_TERMS = (
    "코스",
    "동선",
    "일정",
    "플랜",
    "데이트",
    "주말 계획",
)


def classify_telegram_update(update: dict[str, Any]) -> TelegramIntentDecision:
    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        return TelegramIntentDecision(TelegramIntent.FEEDBACK_CALLBACK, reason="callback_query")

    message = update.get("message")
    if not isinstance(message, dict):
        return TelegramIntentDecision(TelegramIntent.IGNORE, reason="missing_message")

    text = str(message.get("text") or message.get("caption") or "")
    command = parse_command(text)
    if command:
        return TelegramIntentDecision(TelegramIntent.ADMIN_COMMAND, text=text, command=command, reason="command")

    lowered = text.lower()
    if contains_any(lowered, COURSE_TERMS):
        return TelegramIntentDecision(TelegramIntent.COURSE_PLANNING, text=text, reason="course_term")
    if contains_any(lowered, FOOD_TERMS):
        return TelegramIntentDecision(TelegramIntent.FOOD_RECOMMENDATION, text=text, reason="food_term")
    if contains_any(lowered, LIFE_TERMS):
        return TelegramIntentDecision(TelegramIntent.LIFE_REMINDER, text=text, reason="life_term")
    if is_capturable_message(message):
        return TelegramIntentDecision(TelegramIntent.ARCHIVE_CAPTURE, text=text, reason="capturable_message")
    return TelegramIntentDecision(TelegramIntent.IGNORE, text=text, reason="not_capturable")


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)
