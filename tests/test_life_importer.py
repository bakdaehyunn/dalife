from __future__ import annotations

import json

from darchivebot.domains.life import (
    import_honsanam_snapshot,
    load_honsanam_snapshot,
    load_message_pattern,
)
from darchivebot.storage import ArchiveStore


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _legacy_root(tmp_path):
    root = tmp_path / "honsanam"
    root.mkdir()
    (root / "reminders.toml").write_text(
        """
[trash]
enabled = true
weekdays = ["tue", "thu", "sun"]
notify_time = "20:00"

[haircut]
enabled = true
base_date = "2026-05-10"
notify_time = "08:45"
requires_confirmation = true
followup_days = 7
""".strip(),
        encoding="utf-8",
    )
    _write_json(
        root / ".local/config/reminders.json",
        {
            "fixed": {"trash": {"time": "19:30"}},
            "custom": [
                {
                    "id": "water-plants",
                    "title": "화분 물주기",
                    "kind": "weekly",
                    "weekday": "sat",
                    "time": "09:00",
                    "action": "화분 물주기",
                    "note": "거실부터",
                    "enabled": True,
                }
            ],
        },
    )
    sent_key = "trash-2026-08-27:2026-08-27T20:00:00+09:00"
    _write_json(root / ".local/state/sent.json", {"sent": [sent_key]})
    _write_json(
        root / ".local/state/interactions.json",
        {
            "items": {
                "interaction-1": {
                    "interaction_id": "interaction-1",
                    "reminder_id": "trash-2026-08-27",
                    "title": "분리수거",
                    "action": "내놨음",
                    "selected_response": "done",
                    "responded_at": "2026-08-27T20:05:00+09:00",
                    "scheduled_at": "2026-08-27T20:00:00+09:00",
                    "telegram_update_id": 123,
                }
            }
        },
    )
    _write_json(
        root / ".local/state/confirmations.json",
        {
            "telegram_update_offset": 456,
            "items": {
                "haircut-booking-2026-09-06": {
                    "confirmation_id": "haircut-booking-2026-09-06",
                    "reminder_id": "haircut-booking-2026-09-06",
                    "status": "pending",
                    "title": "미용실 예약",
                    "message": "message",
                    "prompt": "미용실 예약했나요?",
                    "scheduled_at": "2026-08-31T08:45:00+09:00",
                    "last_prompted_at": "2026-08-31T08:45:00+09:00",
                    "last_answered_at": None,
                    "last_answer": None,
                    "followup_days": 7,
                }
            },
        },
    )
    return root


def test_import_honsanam_snapshot_preserves_configuration_events_and_responses(tmp_path):
    snapshot = load_honsanam_snapshot(_legacy_root(tmp_path))
    store = ArchiveStore(tmp_path / "state")

    first = import_honsanam_snapshot(store, snapshot)
    second = import_honsanam_snapshot(store, snapshot)

    assert first == second
    assert first.reminders == 13
    assert first.sent_events == 1
    assert first.interaction_events == 1
    assert first.confirmation_events == 1
    assert first.telegram_update_offset == 456
    with store.connect() as conn:
        trash = conn.execute("SELECT * FROM reminders WHERE reminder_key = 'trash'").fetchone()
        custom = conn.execute("SELECT * FROM reminders WHERE reminder_key = 'water-plants'").fetchone()
        events = conn.execute("SELECT * FROM reminder_events ORDER BY event_key").fetchall()
        reminder_count = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]

    assert reminder_count == 13
    assert json.loads(trash["schedule_json"])["time"] == "19:30"
    assert custom["cadence"] == "weekly"
    assert len(events) == 2
    interaction = next(row for row in events if row["event_key"].startswith("honsanam:trash-"))
    assert interaction["status"] == "responded"
    assert interaction["responded_at"] == "2026-08-27T20:05:00+09:00"
    assert json.loads(interaction["response_payload_json"])["selected_response"] == "done"
    confirmation = next(row for row in events if ":confirmation:" in row["event_key"])
    assert confirmation["status"] == "pending_confirmation"
    confirmation_payload = json.loads(confirmation["response_payload_json"])
    assert confirmation_payload["telegram_update_offset"] == 456
    assert confirmation_payload["legacy_confirmation_id"] == "haircut-booking-2026-09-06"
    assert confirmation_payload["title"] == "미용실 예약"
    assert confirmation["due_at"] == "2026-09-07T08:45:00+09:00"


def test_honsanam_import_dry_run_does_not_initialize_or_write_database(tmp_path):
    snapshot = load_honsanam_snapshot(_legacy_root(tmp_path))
    store = ArchiveStore(tmp_path / "state")

    report = import_honsanam_snapshot(store, snapshot, dry_run=True)

    assert report.dry_run is True
    assert report.reminders == 13
    assert not store.path.exists()


def test_honsanam_import_preserves_message_pattern_in_sqlite(tmp_path):
    root = _legacy_root(tmp_path)
    pattern_path = root / ".local/config/message_patterns.json"
    pattern_path.write_text(
        json.dumps(
            {
                "prefix": "내 알림",
                "schedule_label": "시간",
                "action_label": "할 일",
                "note_label": "참고",
            }
        ),
        encoding="utf-8",
    )
    store = ArchiveStore(tmp_path / "state")

    import_honsanam_snapshot(store, load_honsanam_snapshot(root))

    assert load_message_pattern(store).prefix == "내 알림"


def test_honsanam_import_supersedes_older_pending_confirmation_occurrences(tmp_path):
    root = _legacy_root(tmp_path)
    confirmations = {
        "telegram_update_offset": 1,
        "items": {
            "old": {
                "confirmation_id": "haircut-booking-old",
                "reminder_id": "haircut-booking-old",
                "scheduled_at": "2026-07-01T08:45:00+09:00",
                "last_prompted_at": "2026-07-01T08:45:00+09:00",
                "status": "pending",
            },
            "new": {
                "confirmation_id": "haircut-booking-new",
                "reminder_id": "haircut-booking-new",
                "scheduled_at": "2026-08-01T08:45:00+09:00",
                "last_prompted_at": "2026-08-01T08:45:00+09:00",
                "status": "pending",
            },
        },
    }
    _write_json(root / ".local/state/confirmations.json", confirmations)
    store = ArchiveStore(tmp_path / "state")

    import_honsanam_snapshot(store, load_honsanam_snapshot(root), dry_run=False)
    events = store.list_reminder_events(statuses=("pending_confirmation", "superseded"), limit=10)

    assert {str(event["status"]) for event in events} == {"pending_confirmation", "superseded"}
    old = next(event for event in events if str(event["event_key"]).endswith("old"))
    assert json.loads(old["response_payload_json"])["superseded_by_newer_occurrence"] is True
