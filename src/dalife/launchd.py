from __future__ import annotations

import argparse
import plistlib
import subprocess
from pathlib import Path
from typing import Any

from dalife.scheduler import ScheduledJob, launchd_schedule


PATH_VALUE = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LABELS = {
    "telegram": "com.hennei.dalife.telegram",
    "archive-process": "com.hennei.dalife.processor",
    "food-collect": "com.hennei.dalife.food-collect",
    "life-send": "com.hennei.dalife.life-send",
    "revisit-digest": "com.hennei.dalife.digest",
    "project-seed-digest": "com.hennei.dalife.digest.project-seed",
    "weekly-insight": "com.hennei.dalife.digest.weekly",
}

LOG_NAMES = {
    "telegram": "telegram",
    "archive-process": "processor",
    "food-collect": "food-collect",
    "life-send": "life-send",
    "revisit-digest": "digest",
    "project-seed-digest": "digest-project-seed",
    "weekly-insight": "digest-weekly",
}


def launchd_label(job: ScheduledJob) -> str:
    return LABELS[job.name]


def launchd_plist_path(launch_dir: Path, job: ScheduledJob) -> Path:
    return launch_dir / f"{launchd_label(job)}.plist"


def _cadence_payload(job: ScheduledJob) -> dict[str, Any]:
    if job.cadence == "keep_alive":
        return {"KeepAlive": True}
    if job.cadence == "every_5_minutes":
        return {"StartInterval": 300}
    if job.cadence == "daily_09_00":
        return {"StartCalendarInterval": {"Hour": 9, "Minute": 0}}
    if job.cadence == "daily_03_00":
        return {"StartCalendarInterval": {"Hour": 3, "Minute": 0}}
    if job.cadence == "daily_09_30":
        return {"StartCalendarInterval": {"Hour": 9, "Minute": 30}}
    if job.cadence == "daily_18_00":
        return {"StartCalendarInterval": {"Hour": 18, "Minute": 0}}
    raise ValueError(f"unsupported launchd cadence for {job.name}: {job.cadence}")


def launchd_plist(root: Path, job: ScheduledJob) -> dict[str, Any]:
    log_name = LOG_NAMES[job.name]
    program_arguments = [str(root / ".venv" / "bin" / job.command[0]), *job.command[1:]]
    return {
        "Label": launchd_label(job),
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {"PATH": PATH_VALUE},
        **_cadence_payload(job),
        "StandardOutPath": str(root / ".local" / "logs" / f"{log_name}.launchd.out"),
        "StandardErrorPath": str(root / ".local" / "logs" / f"{log_name}.launchd.err"),
    }


def write_launchd_plists(root: Path, launch_dir: Path, *, include_life_sender: bool = False) -> list[Path]:
    launch_dir.mkdir(parents=True, exist_ok=True)
    (root / ".local" / "logs").mkdir(parents=True, exist_ok=True)
    paths = []
    for job in launchd_schedule(include_life_sender=include_life_sender):
        path = launchd_plist_path(launch_dir, job)
        path.write_bytes(plistlib.dumps(launchd_plist(root, job), sort_keys=False))
        paths.append(path)
    return paths


def install_launchd_jobs(root: Path, launch_dir: Path, *, include_life_sender: bool = False) -> list[Path]:
    paths = write_launchd_plists(root, launch_dir, include_life_sender=include_life_sender)
    for path in paths:
        subprocess.run(["launchctl", "unload", str(path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for path in paths:
        subprocess.run(["launchctl", "load", str(path)], check=True)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dalife.launchd")
    parser.add_argument("action", choices=["write", "install"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--launch-dir", type=Path, default=Path.home() / "Library" / "LaunchAgents")
    parser.add_argument(
        "--include-life-sender",
        action="store_true",
        help="explicitly include the native life sender during controlled cutover",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.action == "write":
        paths = write_launchd_plists(root, args.launch_dir, include_life_sender=args.include_life_sender)
    else:
        paths = install_launchd_jobs(root, args.launch_dir, include_life_sender=args.include_life_sender)
    for path in paths:
        print(f"installed {path}" if args.action == "install" else f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
