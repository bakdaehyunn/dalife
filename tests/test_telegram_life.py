from __future__ import annotations

from dalife.domains.life import kst_datetime
from dalife.storage import ArchiveStore
from dalife.telegram_life import upcoming_life_for_telegram


def test_upcoming_life_telegram_reads_custom_schedule_from_sqlite(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    routine = store.upsert_routine(routine_key="water-plants", title="화분 물주기")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="water-plants",
        title="화분 물주기",
        cadence="one-off",
        schedule={"date": "2026-09-05", "time": "09:30"},
        action="화분에 물 주기",
    )

    response = upcoming_life_for_telegram(
        store,
        "생활 알림 보여줘",
        now=kst_datetime("2026-09-04", "09:00"),
    )

    assert "09월 05일 09:30" in response
    assert "화분 물주기" in response


def test_upcoming_life_telegram_filters_matching_title_when_present(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    for key, title in (("water", "화분 물주기"), ("call", "전화하기")):
        routine = store.upsert_routine(routine_key=key, title=title)
        store.upsert_reminder(
            routine_id=routine["id"],
            reminder_key=key,
            title=title,
            cadence="one-off",
            schedule={"date": "2026-09-05", "time": "09:30"},
            action=title,
        )

    response = upcoming_life_for_telegram(
        store,
        "화분 물주기 알림",
        now=kst_datetime("2026-09-04", "09:00"),
    )

    assert "화분 물주기" in response
    assert "전화하기" not in response
