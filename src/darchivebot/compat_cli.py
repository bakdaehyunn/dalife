from __future__ import annotations

import os
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_WORKSPACE = Path("/Users/hennei/workspace")


def momuk_main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not os.environ.get("DARCHIVE_MOMUK_CLI", "").strip():
        try:
            native = native_momuk_args(args)
        except ValueError as exc:
            print(f"momuk recommend: error: {exc}", file=sys.stderr)
            return 2
        if native is not None:
            from darchivebot.cli import main

            return main(native)
    return delegate_cli(
        argv=args,
        env_var="DARCHIVE_MOMUK_CLI",
        candidates=(
            DEFAULT_WORKSPACE / "momukbot" / ".venv" / "bin" / "momuk",
            DEFAULT_WORKSPACE / "momukbot" / ".venv" / "bin" / "python",
        ),
        python_module="momukbot.cli",
        label="momuk",
    )


def native_momuk_args(argv: list[str]) -> list[str] | None:
    if not argv:
        return None
    if argv[0] == "init" and len(argv) == 1:
        return ["init"]
    if argv[0] == "doctor" and len(argv) == 1:
        return ["doctor", "--online"]
    if argv[0] == "rooms" and len(argv) == 1:
        return ["rooms"]
    if argv[0] == "discover-chat":
        return ["discover-chat", *argv[1:]]
    if argv[0] == "send-test":
        return ["send-test", *argv[1:]]
    if argv[0] == "telegram-commands":
        return ["telegram-commands", *argv[1:]]
    if argv[0] == "quota" and len(argv) == 1:
        return ["food", "quota"]
    if argv[0] == "setup" and "--install-launchd" not in argv and not ({"-h", "--help"} & set(argv)):
        return ["setup", *argv[1:]]
    if argv[0] == "parse":
        return ["food", "parse", *argv[1:]]
    if argv[0] != "recommend":
        return None
    if "-h" in argv or "--help" in argv:
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("text", nargs="?")
    parser.add_argument("--area", default="")
    parser.add_argument("--topic", default="")
    parser.add_argument("--count", type=int)
    parser.add_argument("--dry-run", action="store_true")
    values = parser.parse_args(argv[1:])
    if values.text and (values.area or values.topic or values.count is not None):
        raise ValueError("cannot use natural text together with --area, --topic, or --count")
    if values.text:
        from darchivebot.domains.food import parse_food_request

        request = parse_food_request(values.text, default_count=10)
        if not request.area:
            raise ValueError("provide a request containing an area")
        area = request.area
        topic = " ".join(value for value in (request.topic, request.meal_type) if value)
        count = request.count
        occasion = request.occasion
    else:
        if not values.area:
            raise ValueError("provide natural text or --area")
        area = values.area
        topic = values.topic
        count = max(1, min(30, values.count or 10))
        occasion = ""
    native = [
        "food",
        "recommend-local",
        "--area",
        area,
        "--topic",
        topic,
        "--count",
        str(count),
    ]
    if occasion:
        native.extend(["--occasion", occasion])
    if values.dry_run:
        native.append("--dry-run")
    return native


def honsanam_reminder_main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not os.environ.get("DARCHIVE_HONSANAM_REMINDER_CLI", "").strip():
        native = native_honsanam_args(args)
        if native is not None:
            from darchivebot.cli import main

            return main(native)
    return delegate_cli(
        argv=args,
        env_var="DARCHIVE_HONSANAM_REMINDER_CLI",
        candidates=(
            DEFAULT_WORKSPACE / "honsanam-reminder-bot" / ".venv" / "bin" / "honsanam-reminder",
            DEFAULT_WORKSPACE / "honsanam-reminder-bot" / ".venv" / "bin" / "python",
        ),
        python_module="life_reminder.cli",
        label="honsanam-reminder",
    )


NATIVE_HONSANAM_COMMANDS = {
    "preview",
    "run-once",
    "pending",
    "interactions",
    "answer",
    "list",
    "show",
    "enable",
    "disable",
    "remove",
    "add",
    "update",
    "validate",
    "pattern",
}


def native_honsanam_args(argv: list[str]) -> list[str] | None:
    if not argv:
        return None
    if argv[0] == "init" and len(argv) == 1:
        return ["init"]
    if argv[0] == "doctor" and len(argv) == 1:
        return ["doctor", "--online"]
    if argv[0] == "discover-chat":
        return ["discover-chat", *argv[1:]]
    if argv[0] == "send-test" and len(argv) == 1:
        return ["send-test", "--allowed"]
    if argv[0] == "setup" and "--install-launchd" not in argv and not ({"-h", "--help"} & set(argv)):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--non-interactive", action="store_true")
        parser.add_argument("--telegram-bot-token")
        parser.add_argument("--telegram-chat-id")
        parser.add_argument("--timezone")
        parser.parse_args(argv[1:])
        return ["setup", *argv[1:]]
    if argv[0] not in NATIVE_HONSANAM_COMMANDS | {"next"}:
        return None
    args = list(argv)
    if args[0] == "next" and "--date" not in args:
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        args.extend(["--date", now.date().isoformat(), "--time", now.strftime("%H:%M")])
    return ["life", *args]


def delegate_cli(
    *,
    argv: list[str],
    env_var: str,
    candidates: tuple[Path, ...],
    python_module: str,
    label: str,
) -> int:
    configured = os.environ.get(env_var, "").strip()
    if configured:
        return run_command([configured, *argv])

    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.name == "python":
            return run_command([str(candidate), "-m", python_module, *argv])
        return run_command([str(candidate), *argv])

    print(
        f"{label} compatibility wrapper could not find the source CLI. "
        f"Set {env_var} to the existing command path while migration continues.",
        file=sys.stderr,
    )
    return 127


def run_command(command: list[str]) -> int:
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        print(f"failed to run compatibility command: {exc}", file=sys.stderr)
        return 127
