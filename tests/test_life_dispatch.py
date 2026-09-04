from __future__ import annotations

import json

from darchivebot.domains.life import (
    apply_life_callback,
    deliver_due_life_reminders,
    import_honsanam_snapshot,
    kst_datetime,
    life_config_from_store,
    prepare_due_life_dispatches,
    preview_due_life_reminders,
)
from darchivebot.domains.life.importer import HonsanamSnapshot
from darchivebot.storage import ArchiveStore


class FakeLifeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None):
        if self.error is not None:
            raise self.error
        self.messages.append((chat_id, text, reply_markup))
        return {"result": {"message_id": len(self.messages)}}


def _seed_fixed_reminder(store: ArchiveStore, reminder_key: str = "trash") -> None:
    routine = store.upsert_routine(
        routine_key=reminder_key,
        title=reminder_key,
        description="",
    )
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key=reminder_key,
        title=reminder_key,
        cadence="fixed",
        schedule={},
        action=reminder_key,
    )


def test_prepare_due_dispatch_is_idempotent_after_event_is_sent(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store)
    now = kst_datetime("2026-08-30", "20:00")

    dispatches = prepare_due_life_dispatches(store, now)
    assert len(dispatches) == 1
    assert dispatches[0].event["status"] == "pending"
    assert dispatches[0].reply_markup["inline_keyboard"][0][0]["callback_data"].startswith("life:")

    store.update_reminder_event_response(
        event_id=dispatches[0].event["id"],
        status="sent",
        response_payload=json.loads(dispatches[0].event["response_payload_json"]),
        sent_at=now.isoformat(),
    )
    assert prepare_due_life_dispatches(store, now) == []


def test_native_life_callback_transitions_regular_event(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store)
    dispatch = prepare_due_life_dispatches(store, kst_datetime("2026-08-30", "20:00"))[0]

    result = apply_life_callback(
        store,
        f"life:{dispatch.event['id']}:done",
        responded_at="2026-08-30T11:01:00+00:00",
    )

    assert result is not None
    assert result.event["status"] == "responded"
    assert json.loads(result.event["response_payload_json"])["selected_response"] == "done"


def test_native_confirmation_no_remains_pending_for_followup(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store, "haircut")
    dispatch = prepare_due_life_dispatches(store, kst_datetime("2026-08-31", "08:45"))[0]

    result = apply_life_callback(
        store,
        f"life:{dispatch.event['id']}:no",
        responded_at="2026-09-06T23:46:00+00:00",
    )

    assert result is not None
    assert result.event["status"] == "pending_confirmation"
    assert result.event["due_at"] == "2026-09-14T08:46:00+09:00"


def test_pending_confirmation_is_sent_again_only_when_followup_is_due(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store, "haircut")
    initial_at = kst_datetime("2026-08-31", "08:45")
    client = FakeLifeClient()
    first = deliver_due_life_reminders(store, client, chat_id="123", now=initial_at)
    result = apply_life_callback(
        store,
        f"life:{first.event_ids[0]}:no",
        responded_at="2026-08-31T08:46:00+09:00",
    )
    assert result is not None

    early = deliver_due_life_reminders(
        store,
        client,
        chat_id="123",
        now=kst_datetime("2026-09-07", "08:45"),
    )
    due = deliver_due_life_reminders(
        store,
        client,
        chat_id="123",
        now=kst_datetime("2026-09-07", "08:46"),
    )

    assert early.due == 0
    assert (due.due, due.sent) == (1, 1)
    assert len(client.messages) == 2


def test_dry_run_preview_includes_due_confirmation_without_writing(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store, "haircut")
    initial_at = kst_datetime("2026-08-31", "08:45")
    dispatch = prepare_due_life_dispatches(store, initial_at)[0]
    apply_life_callback(
        store,
        f"life:{dispatch.event['id']}:no",
        responded_at="2026-08-31T08:46:00+09:00",
    )

    before = store.get_reminder_event(event_id=dispatch.event["id"])
    preview = preview_due_life_reminders(store, kst_datetime("2026-09-07", "08:46"))
    after = store.get_reminder_event(event_id=dispatch.event["id"])

    assert len(preview) == 1
    assert preview[0].reminder_id == dispatch.event["event_key"]
    assert dict(after) == dict(before)


def test_legacy_interaction_callback_updates_imported_event(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    snapshot = HonsanamSnapshot(
        root=tmp_path,
        config={},
        management={"fixed": {}, "custom": []},
        sent_keys=(),
        interactions=(
            {
                "interaction_id": "old-interaction",
                "reminder_id": "trash-2026-08-30",
                "scheduled_at": "2026-08-30T20:00:00+09:00",
            },
        ),
        confirmations=(),
    )
    import_honsanam_snapshot(store, snapshot)

    result = apply_life_callback(
        store,
        "interact:old-interaction:later",
        responded_at="2026-08-30T11:01:00+00:00",
    )

    assert result is not None
    assert result.event["status"] == "deferred"


def test_dispatch_uses_sqlite_schedule_override_instead_of_defaults(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    routine = store.upsert_routine(routine_key="trash", title="Trash", description="")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="trash",
        title="Late trash",
        cadence="trash",
        schedule={"time": "22:15", "weekdays": ["sun"]},
        action="Take it out",
    )

    assert prepare_due_life_dispatches(store, kst_datetime("2026-08-30", "20:00")) == []
    dispatches = prepare_due_life_dispatches(store, kst_datetime("2026-08-30", "22:15"))
    assert len(dispatches) == 1
    assert dispatches[0].title == "Late trash"


def test_sqlite_custom_weekly_reminder_is_scheduled(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    routine = store.upsert_routine(routine_key="water-plants", title="Plants", description="")
    store.upsert_reminder(
        routine_id=routine["id"],
        reminder_key="water-plants",
        title="Water plants",
        cadence="weekly",
        schedule={"time": "09:10", "weekday": "sun"},
        action="Water the plants",
        note="Check soil first",
    )

    config = life_config_from_store(store)
    assert config["custom"][0]["id"] == "water-plants"
    dispatches = prepare_due_life_dispatches(store, kst_datetime("2026-08-30", "09:10"))
    assert len(dispatches) == 1
    assert dispatches[0].title == "Water plants"
    assert "Water the plants" in dispatches[0].message


def test_delivery_claims_sends_and_does_not_send_occurrence_twice(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store)
    client = FakeLifeClient()
    now = kst_datetime("2026-08-30", "20:00")

    first = deliver_due_life_reminders(store, client, chat_id="123", now=now)
    second = deliver_due_life_reminders(store, client, chat_id="123", now=now)

    assert (first.due, first.sent, first.failed) == (1, 1, 0)
    assert (second.due, second.sent, second.failed) == (0, 0, 0)
    assert len(client.messages) == 1
    event = store.get_reminder_event(event_id=first.event_ids[0])
    assert event is not None
    assert event["status"] == "sent"
    assert event["telegram_message_id"] == "1"


def test_delivery_failure_is_persisted_and_retryable(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    _seed_fixed_reminder(store)
    now = kst_datetime("2026-08-30", "20:00")

    failed = deliver_due_life_reminders(
        store,
        FakeLifeClient(RuntimeError("network down")),
        chat_id="123",
        now=now,
    )
    retried = deliver_due_life_reminders(store, FakeLifeClient(), chat_id="123", now=now)

    assert (failed.sent, failed.failed) == (0, 1)
    assert failed.errors == ("network down",)
    assert (retried.sent, retried.failed) == (1, 0)
