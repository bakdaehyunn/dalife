from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from darchivebot.config import Settings


LEGACY_LIFE_LABELS = (
    "com.hennei.honsanam-reminder-bot.sender",
    "com.hennei.honsanam-reminder-bot.replies",
)
DARCHIVE_TELEGRAM_LABEL = "com.hennei.darchivebot.telegram"
DARCHIVE_LIFE_LABEL = "com.hennei.darchivebot.life-send"


@dataclass(frozen=True)
class LaunchdSnapshot:
    loaded_labels: frozenset[str]
    present_plists: frozenset[str]


def inspect_launchd(launch_dir: Path | None = None) -> LaunchdSnapshot:
    directory = launch_dir or Path.home() / "Library" / "LaunchAgents"
    result = subprocess.run(
        ["launchctl", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    loaded = frozenset(
        line.rsplit("\t", 1)[-1].strip()
        for line in result.stdout.splitlines()
        if "\t" in line
    )
    present = frozenset(path.stem for path in directory.glob("*.plist")) if directory.exists() else frozenset()
    return LaunchdSnapshot(loaded_labels=loaded, present_plists=present)


def cutover_report(
    settings: Settings,
    store: Any,
    *,
    snapshot: LaunchdSnapshot,
    now: datetime,
) -> dict[str, object]:
    confirmation_events = store.list_reminder_events(statuses=("pending_confirmation",), limit=10_000)
    overdue = [event for event in confirmation_events if datetime.fromisoformat(str(event["due_at"])) <= now]

    checks = [
        _check(
            "legacy_life_jobs_stopped",
            not any(label in snapshot.loaded_labels for label in LEGACY_LIFE_LABELS),
            "Stop both legacy Honsanam sender and reply agents before native activation.",
        ),
        _check(
            "native_personal_telegram_enabled",
            settings.native_personal_telegram_enabled,
            "Set DARCHIVE_NATIVE_PERSONAL_TELEGRAM=true only for the controlled cutover.",
        ),
        _check(
            "darchive_telegram_loaded",
            DARCHIVE_TELEGRAM_LABEL in snapshot.loaded_labels,
            "Load the Darchive Telegram agent before retiring the legacy reply watcher.",
        ),
        _check(
            "life_sender_plist_ready",
            DARCHIVE_LIFE_LABEL in snapshot.present_plists,
            "Generate the native life sender plist with the explicit --include-life-sender flag.",
        ),
        _check(
            "no_overdue_confirmations",
            not overdue,
            "Resolve or explicitly migrate overdue confirmation follow-ups before activation.",
        ),
    ]
    blockers = [check for check in checks if not check["passed"]]
    return {
        "ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "state": {
            "legacy_loaded_labels": sorted(set(LEGACY_LIFE_LABELS) & snapshot.loaded_labels),
            "legacy_present_plists": sorted(set(LEGACY_LIFE_LABELS) & snapshot.present_plists),
            "pending_confirmations": len(confirmation_events),
            "overdue_confirmations": len(overdue),
        },
    }


def _check(name: str, passed: bool, remediation: str) -> dict[str, object]:
    return {"name": name, "passed": passed, "remediation": "" if passed else remediation}
