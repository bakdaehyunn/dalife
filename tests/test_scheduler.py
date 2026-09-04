from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from darchivebot.config import get_settings
from darchivebot.cutover import LaunchdSnapshot, cutover_report
from darchivebot.launchd import launchd_plist, launchd_plist_path, write_launchd_plists
from darchivebot.scheduler import launchd_schedule, schedule_summary, unified_schedule
from darchivebot.storage import ArchiveStore


def test_unified_schedule_includes_required_operational_jobs():
    jobs = {job.name: job for job in unified_schedule()}

    assert jobs["telegram"].command == ("darchive", "telegram")
    assert jobs["archive-process"].command == ("darchive", "process", "--export-graph")
    assert jobs["food-collect"].command == (
        "darchive",
        "food",
        "run-collection",
        "--max-queries",
        "20",
        "--max-quota-cost",
        "20",
    )
    assert jobs["food-collect"].cadence == "daily_03_00"
    assert jobs["food-collect"].launchd_managed is True
    assert jobs["life-send"].launchd_managed is False
    assert jobs["life-send"].command == ("darchive", "life", "run-once")
    assert jobs["feedback-replies"].cadence == "keep_alive"
    assert jobs["feedback-replies"].launchd_managed is False
    assert jobs["revisit-digest"].command == ("darchive", "telegram-digest", "--kind", "revisit")
    assert jobs["project-seed-digest"].command == ("darchive", "telegram-digest", "--kind", "project-seed")
    assert jobs["weekly-insight"].command == ("darchive", "telegram-digest", "--kind", "weekly")


def test_schedule_summary_hides_disabled_future_jobs_by_default():
    names = {row["name"] for row in schedule_summary()}
    all_names = {row["name"] for row in schedule_summary(include_disabled=True)}

    assert "course-suggestions" not in names
    assert "course-suggestions" in all_names


def test_launchd_schedule_only_includes_enabled_executable_jobs():
    names = [job.name for job in launchd_schedule()]

    assert names == [
        "telegram",
        "archive-process",
        "food-collect",
        "revisit-digest",
        "project-seed-digest",
        "weekly-insight",
    ]
    assert "life-send" in {job.name for job in launchd_schedule(include_life_sender=True)}


def test_launchd_plist_is_generated_from_unified_schedule(tmp_path):
    jobs = {job.name: job for job in launchd_schedule()}
    root = Path("/repo")

    telegram = launchd_plist(root, jobs["telegram"])
    processor = launchd_plist(root, jobs["archive-process"])
    food = launchd_plist(root, jobs["food-collect"])
    weekly = launchd_plist(root, jobs["weekly-insight"])

    assert telegram["Label"] == "com.hennei.darchivebot.telegram"
    assert telegram["ProgramArguments"] == ["/repo/.venv/bin/darchive", "telegram"]
    assert telegram["KeepAlive"] is True
    assert processor["Label"] == "com.hennei.darchivebot.processor"
    assert processor["ProgramArguments"] == ["/repo/.venv/bin/darchive", "process", "--export-graph"]
    assert processor["StartInterval"] == 300
    assert food["Label"] == "com.hennei.darchivebot.food-collect"
    assert food["ProgramArguments"] == [
        "/repo/.venv/bin/darchive",
        "food",
        "run-collection",
        "--max-queries",
        "20",
        "--max-quota-cost",
        "20",
    ]
    assert food["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert weekly["ProgramArguments"] == ["/repo/.venv/bin/darchive", "telegram-digest", "--kind", "weekly"]
    assert weekly["StartCalendarInterval"] == {"Hour": 9, "Minute": 30}


def test_write_launchd_plists_uses_known_labels_and_logs(tmp_path):
    root = tmp_path / "repo"
    launch_dir = tmp_path / "agents"

    paths = write_launchd_plists(root, launch_dir)

    assert launchd_plist_path(launch_dir, launchd_schedule()[0]) in paths
    assert (launch_dir / "com.hennei.darchivebot.telegram.plist").exists()
    assert (launch_dir / "com.hennei.darchivebot.processor.plist").exists()
    assert (root / ".local" / "logs").exists()

    cutover_paths = write_launchd_plists(root, launch_dir, include_life_sender=True)
    assert launch_dir / "com.hennei.darchivebot.life-send.plist" in cutover_paths


def test_cutover_report_exposes_live_activation_blockers(tmp_path):
    settings = replace(get_settings(tmp_path), native_personal_telegram_enabled=False)
    store = ArchiveStore(settings.state_dir)
    reminder = store.upsert_reminder(
        reminder_key="cutover-test",
        title="Cutover test",
        action="Review",
        cadence="one_off",
        schedule={},
    )
    store.upsert_reminder_event(
        reminder_id=str(reminder["id"]),
        event_key="legacy-confirmation",
        due_at="2026-09-01T08:00:00+09:00",
        status="pending_confirmation",
    )

    report = cutover_report(
        settings,
        store,
        snapshot=LaunchdSnapshot(
            loaded_labels=frozenset({"com.hennei.honsanam-reminder-bot.sender"}),
            present_plists=frozenset({"com.hennei.honsanam-reminder-bot.sender"}),
        ),
        now=datetime.fromisoformat("2026-09-04T12:00:00+09:00"),
    )

    assert report["ready"] is False
    assert {item["name"] for item in report["blockers"]} == {
        "legacy_life_jobs_stopped",
        "native_personal_telegram_enabled",
        "darchive_telegram_loaded",
        "life_sender_plist_ready",
        "no_overdue_confirmations",
    }
    assert report["state"]["overdue_confirmations"] == 1


def test_cutover_report_can_reach_ready_state(tmp_path):
    settings = replace(get_settings(tmp_path), native_personal_telegram_enabled=True)
    store = ArchiveStore(settings.state_dir)
    report = cutover_report(
        settings,
        store,
        snapshot=LaunchdSnapshot(
            loaded_labels=frozenset({"com.hennei.darchivebot.telegram"}),
            present_plists=frozenset({"com.hennei.darchivebot.life-send"}),
        ),
        now=datetime.fromisoformat("2026-09-04T12:00:00+09:00"),
    )

    assert report["ready"] is True
    assert report["blockers"] == []
