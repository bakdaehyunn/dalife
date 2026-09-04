from __future__ import annotations

from darchivebot.domains.life import (
    FIXED_REMINDER_ORDER,
    MessagePattern,
    default_reminder_config,
    due_reminders,
    get_fixed_spec,
    kst_datetime,
    scheduled_reminders_near,
    upcoming_reminders,
)
from darchivebot.domains.life.messages import card
from darchivebot.domains.life.schedule import apply_haircut_weekend_policy, parse_date


def test_life_domain_preserves_honsanam_default_reminder_catalog():
    assert FIXED_REMINDER_ORDER == (
        "haircut",
        "fingernails",
        "toenails",
        "trash",
        "mac-status",
        "weekend-cleaning",
        "bedding-wash",
        "bathroom-cleaning",
        "nose-hair",
        "eyebrows",
        "earwax",
        "toothbrush",
    )
    haircut = get_fixed_spec("haircut")

    assert haircut.title == "미용실 예약"
    assert haircut.requires_confirmation
    assert haircut.interaction_labels == (("예약했음", "yes"), ("아직", "no"))


def test_life_message_card_preserves_honsanam_pattern_shape():
    message = card(
        "분리수거",
        "8월 30일 일요일 20:00",
        "오늘 분리수거 내놓기",
        "종량제 봉투도 확인",
        MessagePattern(),
    )

    assert message == "\n".join(
        [
            "생활알림 | 분리수거",
            "",
            "언제",
            "8월 30일 일요일 20:00",
            "",
            "해야 할 일",
            "오늘 분리수거 내놓기",
            "",
            "관리 포인트",
            "종량제 봉투도 확인",
        ]
    )


def test_due_reminders_includes_trash_on_default_sunday_window():
    reminders = due_reminders(
        kst_datetime("2026-08-30", "20:00"),
        default_reminder_config(),
    )

    assert [reminder.reminder_id for reminder in reminders] == ["trash-2026-08-30"]
    assert reminders[0].sent_key.endswith("2026-08-30T20:00:00+09:00")
    assert "생활알림 | 분리수거" in reminders[0].message


def test_upcoming_reminders_lists_default_schedule_window_without_duplicates():
    reminders = upcoming_reminders(
        kst_datetime("2026-08-29", "00:00"),
        default_reminder_config(),
        days=2,
    )
    keys = [reminder.sent_key for reminder in reminders]
    ids = [reminder.reminder_id for reminder in reminders]
    scheduled_at = [reminder.scheduled_at for reminder in reminders]

    assert len(keys) == len(set(keys))
    assert scheduled_at == sorted(scheduled_at)
    assert "mac-status-2026-08-29" in ids
    assert "weekend-cleaning-2026-08-29" in ids
    assert "trash-2026-08-30" in ids


def test_scheduled_reminders_include_default_saturday_routines():
    reminders = scheduled_reminders_near(
        kst_datetime("2026-08-29", "10:00"),
        default_reminder_config(),
    )
    ids = {reminder.reminder_id for reminder in reminders}

    assert "mac-status-2026-08-29" in ids
    assert "weekend-cleaning-2026-08-29" in ids


def test_interval_reminders_preserve_default_honsanam_dates():
    reminders = scheduled_reminders_near(
        kst_datetime("2026-08-28", "20:40"),
        default_reminder_config(),
    )
    ids = {reminder.reminder_id for reminder in reminders}

    assert "nose-hair-2026-08-28" in ids
    assert "eyebrows-2026-08-28" in ids


def test_haircut_weekend_policy_preserves_previous_sunday_behavior():
    assert apply_haircut_weekend_policy(parse_date("2026-06-10"), "previous_sunday").isoformat() == "2026-06-07"
    assert apply_haircut_weekend_policy(parse_date("2026-06-13"), "previous_sunday").isoformat() == "2026-06-13"


def test_custom_one_off_weekly_and_interval_schedules_are_preserved():
    config = default_reminder_config()
    config["custom"] = [
        {"id": "once", "kind": "one-off", "date": "2026-08-30", "time": "09:00", "title": "Once", "action": "Do once"},
        {"id": "weekly", "kind": "weekly", "weekday": "sun", "time": "09:00", "title": "Weekly", "action": "Do weekly"},
        {"id": "interval", "kind": "interval", "base_date": "2026-08-23", "days": 7, "time": "09:00", "title": "Interval", "action": "Do interval"},
    ]

    reminders = due_reminders(kst_datetime("2026-08-30", "09:00"), config)

    assert {item.reminder_id for item in reminders} == {"once", "weekly", "interval"}
