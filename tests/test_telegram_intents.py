from __future__ import annotations

from dalife.telegram_intents import TelegramIntent, classify_telegram_update


def test_classify_callback_as_feedback_intent():
    decision = classify_telegram_update({"callback_query": {"id": "cb-1", "data": "dai:prompt:keep"}})

    assert decision.intent == TelegramIntent.FEEDBACK_CALLBACK
    assert decision.reason == "callback_query"


def test_classify_command_as_admin_command_intent():
    decision = classify_telegram_update({"message": {"text": "/chatid@dalife hello"}})

    assert decision.intent == TelegramIntent.ADMIN_COMMAND
    assert decision.command == "/chatid"


def test_classify_food_life_and_course_intents():
    assert classify_telegram_update({"message": {"text": "신정동 맛집 추천"}}).intent == TelegramIntent.FOOD_RECOMMENDATION
    assert classify_telegram_update({"message": {"text": "이번 주 청소 알림 보여줘"}}).intent == TelegramIntent.LIFE_REMINDER
    assert classify_telegram_update({"message": {"text": "이태원 저녁 코스 짜줘"}}).intent == TelegramIntent.COURSE_PLANNING


def test_classify_plain_capturable_message_as_archive_capture():
    decision = classify_telegram_update({"message": {"text": "나중에 다시 볼 아카이브 메모"}})

    assert decision.intent == TelegramIntent.ARCHIVE_CAPTURE
    assert decision.reason == "capturable_message"


def test_classify_empty_service_message_as_ignore():
    decision = classify_telegram_update({"message": {"new_chat_members": [{"id": 1}]}})

    assert decision.intent == TelegramIntent.IGNORE
