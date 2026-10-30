from __future__ import annotations

from pathlib import Path

from dalife.launchd import launchd_plist, launchd_plist_path, write_launchd_plists
from dalife.scheduler import launchd_schedule, schedule_summary, unified_schedule


def test_unified_schedule_includes_required_operational_jobs():
    jobs = {job.name: job for job in unified_schedule()}

    assert jobs["telegram"].command == ("dalife", "telegram")
    assert jobs["archive-process"].command == ("dalife", "archive", "process")
    assert jobs["archive-process"].cadence == "every_15_minutes"
    assert jobs["food-collect"].command == (
        "dalife",
        "food",
        "run-collection",
        "--max-queries",
        "20",
        "--max-quota-cost",
        "20",
    )
    assert jobs["food-collect"].cadence == "daily_03_00"
    assert jobs["food-collect"].launchd_managed is True
    assert jobs["life-send"].launchd_managed is True
    assert jobs["life-send"].command == ("dalife", "life", "run-once")
    assert jobs["life-send"].cadence == "every_15_minutes"


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
        "life-send",
    ]


def test_launchd_plist_is_generated_from_unified_schedule(tmp_path):
    jobs = {job.name: job for job in launchd_schedule()}
    root = Path("/repo")

    telegram = launchd_plist(root, jobs["telegram"])
    processor = launchd_plist(root, jobs["archive-process"])
    food = launchd_plist(root, jobs["food-collect"])
    life = launchd_plist(root, jobs["life-send"])

    assert telegram["Label"] == "com.hennei.dalife.telegram"
    assert telegram["ProgramArguments"] == ["/repo/.venv/bin/dalife", "telegram"]
    assert telegram["KeepAlive"] is True
    assert processor["Label"] == "com.hennei.dalife.processor"
    assert processor["ProgramArguments"] == ["/repo/.venv/bin/dalife", "archive", "process"]
    assert processor["StartInterval"] == 900
    assert food["Label"] == "com.hennei.dalife.food-collect"
    assert food["ProgramArguments"] == [
        "/repo/.venv/bin/dalife",
        "food",
        "run-collection",
        "--max-queries",
        "20",
        "--max-quota-cost",
        "20",
    ]
    assert food["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}
    assert life["Label"] == "com.hennei.dalife.life-send"
    assert life["ProgramArguments"] == ["/repo/.venv/bin/dalife", "life", "run-once"]
    assert life["StartInterval"] == 900


def test_write_launchd_plists_uses_known_labels_and_logs(tmp_path):
    root = tmp_path / "repo"
    launch_dir = tmp_path / "agents"

    paths = write_launchd_plists(root, launch_dir)

    assert launchd_plist_path(launch_dir, launchd_schedule()[0]) in paths
    assert (launch_dir / "com.hennei.dalife.telegram.plist").exists()
    assert (launch_dir / "com.hennei.dalife.processor.plist").exists()
    assert (launch_dir / "com.hennei.dalife.life-send.plist").exists()
    assert (root / ".local" / "logs").exists()

    assert launch_dir / "com.hennei.dalife.life-send.plist" in paths
