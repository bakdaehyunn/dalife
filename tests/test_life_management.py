from __future__ import annotations

import pytest

from darchivebot.domains.life import (
    LifeValidationError,
    add_custom_reminder,
    load_message_pattern,
    remove_custom_reminder,
    set_reminder_enabled,
    update_reminder,
    update_message_pattern,
    validate_stored_reminders,
)
from darchivebot.storage import ArchiveStore


def test_custom_reminder_crud_is_sqlite_backed(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    added = add_custom_reminder(
        store,
        {
            "id": "water-plants",
            "title": "Water plants",
            "kind": "weekly",
            "time": "09:30",
            "weekday": "sun",
            "action": "Water plants",
            "note": "Check soil",
        },
    )
    assert added["enabled"] == 1

    disabled = set_reminder_enabled(store, "water-plants", False)
    updated = update_reminder(
        store,
        "water-plants",
        {"title": "Water all plants", "time": "10:00"},
    )
    assert disabled["enabled"] == 0
    assert updated["title"] == "Water all plants"
    assert updated["enabled"] == 0
    assert validate_stored_reminders(store) == []

    remove_custom_reminder(store, "water-plants")
    assert store.get_reminder_by_key(reminder_key="water-plants") is None


def test_management_rejects_invalid_custom_and_fixed_removal(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    with pytest.raises(LifeValidationError, match="weekday"):
        add_custom_reminder(
            store,
            {
                "id": "water-plants",
                "title": "Water plants",
                "kind": "weekly",
                "time": "09:30",
                "weekday": "someday",
                "action": "Water plants",
            },
        )
    routine = store.upsert_routine(routine_key="trash", title="Trash")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="trash",
        title="Trash",
        cadence="trash",
        schedule={"time": "20:00", "weekdays": ["sun"]},
        action="Take trash out",
    )
    with pytest.raises(LifeValidationError, match="cannot remove fixed"):
        remove_custom_reminder(store, "trash")


def test_message_pattern_is_persisted_in_sqlite(tmp_path):
    store = ArchiveStore(tmp_path / "state")

    updated = update_message_pattern(store, prefix="내 알림", action_label="할 일")
    loaded = load_message_pattern(store)

    assert updated == loaded
    assert loaded.prefix == "내 알림"
    assert loaded.action_label == "할 일"
    assert loaded.schedule_label == "언제"
