from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from typing import Any

from darchivebot.storage import ArchiveStore
from darchivebot.telegram import TelegramCaptureBot, extract_attachments, is_capturable_message, parse_command, send_bot_prompt

from conftest import make_settings


class FakeTelegramApi:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.callback_answers: list[tuple[str, str]] = []
        self.edited_reply_markups: list[tuple[str, int, dict[str, Any] | None]] = []

    def get_file(self, file_id: str) -> dict[str, Any]:
        return {"file_path": f"photos/{file_id}.jpg"}

    def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"image")

    def send_message(self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return {"result": {"message_id": len(self.messages)}}

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        self.callback_answers.append((callback_query_id, text))

    def edit_message_reply_markup(
        self,
        chat_id: str,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.edited_reply_markups.append((chat_id, message_id, reply_markup))


def test_parse_command_handles_bot_suffix():
    assert parse_command("/chatid@darchivebot hello") == "/chatid"
    assert parse_command("hello") == ""


def test_extract_photo_attachment_uses_largest_photo():
    message = {
        "photo": [
            {"file_id": "small", "file_unique_id": "s", "file_size": 10},
            {"file_id": "large", "file_unique_id": "l", "file_size": 20},
        ]
    }
    attachments = extract_attachments(message)
    assert attachments[0]["file_id"] == "large"


def test_capture_photo_downloads_media_and_records_file(tmp_path):
    settings = make_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    api = FakeTelegramApi()
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 7,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private", "first_name": "Me"},
                "from": {"id": 42, "first_name": "Me"},
                "caption": "캡처 내용",
                "photo": [{"file_id": "photo1", "file_unique_id": "p1", "file_size": 100}],
            },
        }
    )

    assert capture_id is not None
    files = store.files_for_capture(capture_id)
    assert len(files) == 1
    assert files[0]["download_status"] == "downloaded"
    assert Path(files[0]["local_path"]).exists()


def test_food_intent_still_falls_back_to_archive_capture_until_handlers_are_verified(tmp_path):
    settings = make_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    bot = TelegramCaptureBot(settings, store, api=FakeTelegramApi())  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 8,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private", "first_name": "Me"},
                "from": {"id": 42, "first_name": "Me"},
                "text": "신정동 맛집 추천",
            },
        }
    )

    assert capture_id is not None
    assert store.get_capture(capture_id)["text"] == "신정동 맛집 추천"


def test_enabled_native_food_intent_sends_local_recommendation_and_feedback_persists(tmp_path):
    settings = replace(make_settings(tmp_path), native_personal_telegram_enabled=True)
    store = ArchiveStore(settings.state_dir)
    area = store.upsert_area(name="신정동", normalized_name="신정동")
    place = store.upsert_place(
        provider="kakao_local",
        provider_place_id="place-1",
        name="동네 식당",
        normalized_name="동네식당",
        area_id=area["id"],
        category="한식",
    )
    api = FakeTelegramApi()
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 8,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private", "first_name": "Me"},
                "from": {"id": 42, "first_name": "Me"},
                "text": "신정동 한식 맛집 1곳 추천",
            },
        }
    )

    assert capture_id is None
    assert store.list_captures(10) == []
    assert "동네 식당" in api.messages[0]["text"]
    callback_data = api.messages[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    bot.handle_update(
        {
            "update_id": 2,
            "callback_query": {
                "id": "food-callback",
                "from": {"id": 42},
                "message": {"message_id": 9, "chat": {"id": 123, "type": "private"}},
                "data": callback_data,
            },
        }
    )

    feedback = store.list_user_feedback(domain="food", limit=10)
    assert feedback[0]["place_id"] == place["id"]
    assert api.callback_answers[-1] == ("food-callback", "Saved: Liked")


def test_enabled_native_course_intent_persists_and_sends_plan_without_capture(tmp_path):
    settings = replace(make_settings(tmp_path), native_personal_telegram_enabled=True)
    store = ArchiveStore(settings.state_dir)
    area = store.upsert_area(name="이태원", normalized_name="이태원")
    place = store.upsert_place(
        provider="kakao_local",
        provider_place_id="course-place",
        name="코스 식당",
        normalized_name="코스식당",
        area_id=area["id"],
        category="저녁",
    )
    api = FakeTelegramApi()
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 3,
            "message": {
                "message_id": 10,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private", "first_name": "Me"},
                "from": {"id": 42, "first_name": "Me"},
                "text": "이태원 저녁 코스 짜줘",
            },
        }
    )

    assert capture_id is None
    assert store.list_captures(10) == []
    assert "이태원 코스" in api.messages[0]["text"]
    assert "코스 식당" in api.messages[0]["text"]
    with store.connect() as conn:
        plan = conn.execute("SELECT * FROM course_plans ORDER BY generated_at DESC LIMIT 1").fetchone()
    assert plan is not None
    stops = store.list_course_plan_stops(course_plan_id=plan["id"])
    assert stops[0]["place_id"] == place["id"]


def test_enabled_native_life_intent_uses_life_handler_without_archive_capture(
    tmp_path,
    monkeypatch,
):
    settings = replace(make_settings(tmp_path), native_personal_telegram_enabled=True)
    store = ArchiveStore(settings.state_dir)
    api = FakeTelegramApi()
    monkeypatch.setattr(
        "darchivebot.telegram.upcoming_life_for_telegram",
        lambda store, text, now: "예정된 생활 알림",
    )
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 4,
            "message": {
                "message_id": 11,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 42},
                "text": "이번 주 청소 알림 보여줘",
            },
        }
    )

    assert capture_id is None
    assert store.list_captures(10) == []
    assert api.messages[0]["text"] == "예정된 생활 알림"


def test_service_event_and_empty_messages_are_not_capturable():
    assert not is_capturable_message({"message_id": 1, "new_chat_members": [{"id": 1}]})
    assert not is_capturable_message({"message_id": 2})
    assert is_capturable_message({"message_id": 3, "text": "hello"})


def test_handle_update_ignores_service_event(tmp_path):
    settings = make_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    bot = TelegramCaptureBot(settings, store, api=FakeTelegramApi())  # type: ignore[arg-type]

    capture_id = bot.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 9,
                "date": 1_700_000_000,
                "chat": {"id": 123, "type": "private", "first_name": "Me"},
                "from": {"id": 42, "first_name": "Me"},
                "new_chat_members": [{"id": 100, "is_bot": True}],
            },
        }
    )

    assert capture_id is None
    assert store.list_captures(10) == []


def test_send_bot_prompt_uses_inline_keyboard_and_marks_sent(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    api = FakeTelegramApi()
    prompt = store.create_bot_prompt(
        prompt_key="telegram:prompt",
        chat_id="123",
        prompt_type="project_seed_candidate",
        title="Project candidate",
        body="Short summary only",
        recommended_action="Choose",
        choices=[
            {"choice": "project_seed", "label": "Project seed"},
            {"choice": "ignore", "label": "Ignore"},
        ],
    )

    result = send_bot_prompt(api, store, {**dict(prompt), "choices": [{"choice": "project_seed", "label": "Project seed"}, {"choice": "ignore", "label": "Ignore"}]})  # type: ignore[arg-type]

    assert result["message_id"] == "1"
    assert api.messages[0]["chat_id"] == "123"
    assert "Project candidate" in api.messages[0]["text"]
    keyboard = api.messages[0]["reply_markup"]["inline_keyboard"]
    assert keyboard[0][0]["text"] == "Project seed"
    assert keyboard[0][0]["callback_data"].startswith(f"dai:{prompt['id']}:")
    sent = store.get_bot_prompt(prompt["id"])
    assert sent is not None
    assert sent["status"] == "sent"


def test_callback_buttons_record_each_choice_idempotently(tmp_path):
    settings = make_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    api = FakeTelegramApi()
    choices = [
        {"choice": "project_seed", "label": "Project seed"},
        {"choice": "revisit", "label": "Revisit"},
        {"choice": "keep", "label": "Keep"},
        {"choice": "needs_review", "label": "Needs review"},
        {"choice": "ignore", "label": "Ignore"},
    ]
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    for index, choice in enumerate(choices, start=1):
        prompt = store.create_bot_prompt(
            prompt_key=f"callback:{choice['choice']}",
            chat_id="123",
            prompt_type="review_classification",
            title="Prompt",
            body="Body",
            recommended_action="Choose",
            choices=choices,
        )
        bot.handle_update(
            {
                "update_id": index,
                "callback_query": {
                    "id": f"cb-{index}",
                    "from": {"id": 42},
                    "message": {"message_id": index, "chat": {"id": 123, "type": "private"}},
                    "data": f"dai:{prompt['id']}:{choice['choice']}",
                },
            }
        )
        row = store.get_bot_prompt(prompt["id"])
        assert row is not None
        assert row["selected_choice"] == choice["choice"]

    assert len(api.callback_answers) == len(choices)
    assert all(answer[1].startswith("Saved:") for answer in api.callback_answers)


def test_life_callback_is_routed_before_archive_prompt_callbacks(tmp_path):
    settings = make_settings(tmp_path)
    store = ArchiveStore(settings.state_dir)
    api = FakeTelegramApi()
    routine = store.upsert_routine(routine_key="trash", title="Trash", description="")
    reminder = store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="trash",
        title="Trash",
        cadence="fixed",
        schedule={},
        action="Take out trash",
    )
    event = store.upsert_reminder_event(
        reminder_id=reminder["id"],
        event_key="life:test",
        due_at="2026-08-30T20:00:00+09:00",
        status="sent",
        response_payload={"actions": ["done", "later"]},
    )
    bot = TelegramCaptureBot(settings, store, api=api)  # type: ignore[arg-type]

    bot.handle_update(
        {
            "update_id": 10,
            "callback_query": {
                "id": "life-callback",
                "from": {"id": 42},
                "message": {"message_id": 99, "chat": {"id": 123, "type": "private"}},
                "data": f"life:{event['id']}:done",
            },
        }
    )

    updated = store.get_reminder_event(event_id=event["id"])
    assert updated is not None
    assert updated["status"] == "responded"
    assert api.callback_answers == [("life-callback", "완료로 기록했어요.")]
    assert api.edited_reply_markups == [("123", 99, None)]
