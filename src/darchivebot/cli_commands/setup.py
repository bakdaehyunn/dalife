from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from darchivebot.cli_formatting import mask_identifier
from darchivebot.config import DEFAULT_ENV_FILE, Settings, ensure_local_dirs, get_settings, update_env_values
from darchivebot.doctor import run_doctor
from darchivebot.storage import ArchiveStore
from darchivebot.telegram import TelegramApiClient, discover_chat_candidates


def init_cmd(settings: Settings, store: ArchiveStore) -> int:
    ensure_local_dirs(settings)
    store.init_db()
    if not DEFAULT_ENV_FILE.exists():
        DEFAULT_ENV_FILE.write_text(Path(settings.root / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        print(f"created {DEFAULT_ENV_FILE}")
    print(f"initialized SQLite at {store.path}")
    return 0

def setup_cmd_impl(
    settings: Settings,
    *,
    dry_run: bool,
    non_interactive: bool,
    telegram_bot_token: str | None,
    telegram_chat_id: str | None,
    telegram_admin_user_id: str | None,
    allow_all_chats: bool,
    install_launchd: bool,
    timezone: str | None = None,
    naver_client_id: str | None = None,
    naver_client_secret: str | None = None,
    kakao_rest_api_key: str | None = None,
    codex_bin: str | None = None,
    env_file: Path,
    settings_loader: Any,
    doctor: Any,
) -> int:
    print("==> Preparing local files")
    if dry_run:
        print(f"[dry-run] ensure local directories and SQLite under {settings.root}")
    else:
        ensure_local_dirs(settings)
        ArchiveStore(settings.state_dir).init_db()

    token = choose_setup_value(
        label="Telegram bot token",
        current=settings.telegram_bot_token,
        provided=telegram_bot_token,
        secret=True,
        non_interactive=non_interactive,
    )
    admin_user_id = choose_setup_value(
        label="Telegram admin user id",
        current=",".join(settings.telegram_admin_user_ids),
        provided=telegram_admin_user_id,
        secret=False,
        non_interactive=non_interactive,
    )
    chat_id = telegram_chat_id or ",".join(settings.telegram_allowed_chat_ids)
    life_timezone = (timezone or settings.life_timezone).strip()
    try:
        ZoneInfo(life_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"[FAIL] invalid timezone: {life_timezone}")
        return 1
    if not chat_id and token:
        chat_id = discover_chat_for_setup(token, dry_run=dry_run, non_interactive=non_interactive)
    if not chat_id and not non_interactive:
        chat_id = prompt_setup_value("Telegram allowed chat id", "", secret=False)

    if not token:
        print("[FAIL] Telegram bot token is required")
        return 1
    if not chat_id and not allow_all_chats:
        print("[FAIL] Telegram chat id is required unless --allow-all-chats is set")
        return 1

    print("==> Writing .env")
    if dry_run:
        print(f"[dry-run] write {env_file}")
    else:
        write_setup_env(
            env_file,
            telegram_bot_token=token,
            telegram_allowed_chat_ids=chat_id,
            telegram_admin_user_ids=admin_user_id,
            allow_all_chats=allow_all_chats,
            life_timezone=life_timezone,
            provider_values={
                "NAVER_CLIENT_ID": naver_client_id,
                "NAVER_CLIENT_SECRET": naver_client_secret,
                "KAKAO_REST_API_KEY": kakao_rest_api_key,
                "DARCHIVE_CODEX_BIN": codex_bin,
            },
        )

    configured = settings_loader()
    print("==> Running doctor")
    if dry_run:
        print("[dry-run] darchive doctor")
    else:
        code, text = doctor(configured, ArchiveStore(configured.state_dir), online=False)
        print(text)
        if code != 0:
            return code

    if install_launchd:
        return install_launch_agent(settings.root, dry_run=dry_run)
    print("setup complete")
    print("Normal operation: run `scripts/install_launch_agent.sh` so launchd keeps capture running, processes every 5 minutes, and refreshes the semantic graph after successful processing.")
    print("Test/debug mode: run `darchive telegram`, `darchive pending`, or `darchive process` directly when checking behavior.")
    print("For personal archives, a 1:1 Telegram chat is recommended. For groups, disable BotFather Group Privacy.")
    return 0

def choose_setup_value(
    *,
    label: str,
    current: str,
    provided: str | None,
    secret: bool,
    non_interactive: bool,
) -> str:
    if provided is not None:
        return provided.strip()
    if non_interactive:
        return current.strip()
    return prompt_setup_value(label, current, secret=secret)

def prompt_setup_value(label: str, current: str, *, secret: bool) -> str:
    if current:
        prompt = f"{label} [configured]: " if secret else f"{label} [{current}]: "
    else:
        prompt = f"{label}: "
    value = getpass.getpass(prompt) if secret else input(prompt)
    return current if not value else value.strip()

def discover_chat_for_setup(token: str, *, dry_run: bool, non_interactive: bool) -> str:
    print("Telegram chat id can be discovered after the bot receives one message.")
    if dry_run:
        print("[dry-run] darchive discover-chat --plain")
        return ""
    if not non_interactive and not ask_yes_no("Try chat id auto discovery?", default=True):
        return ""
    candidates = discover_chat_candidates(TelegramApiClient(token).get_updates())
    if not candidates:
        return ""
    latest = candidates[-1]
    print(f"discovered chat id: {mask_identifier(latest.chat_id)} ({latest.chat_type or 'unknown'})")
    return latest.chat_id

def write_setup_env(
    env_file: Path,
    *,
    telegram_bot_token: str,
    telegram_allowed_chat_ids: str,
    telegram_admin_user_ids: str,
    allow_all_chats: bool,
    life_timezone: str,
    provider_values: dict[str, str | None] | None = None,
) -> None:
    values = {
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_ALLOWED_CHAT_IDS": telegram_allowed_chat_ids,
        "TELEGRAM_ADMIN_USER_IDS": telegram_admin_user_ids,
        "DARCHIVE_ALLOW_ALL_CHATS": str(allow_all_chats).lower(),
        "DARCHIVE_LIFE_TIMEZONE": life_timezone,
        "DARCHIVE_STATE_DIR": ".local/state",
        "DARCHIVE_LOG_DIR": ".local/logs",
        "DARCHIVE_MEDIA_DIR": ".local/captures",
        "DARCHIVE_CODEX_ENABLED": "true",
        "DARCHIVE_CODEX_BIN": "codex",
        "DARCHIVE_CODEX_MODEL": "",
        "DARCHIVE_CODEX_SANDBOX": "read-only",
        "DARCHIVE_CODEX_EPHEMERAL": "true",
        "DARCHIVE_CODEX_TIMEOUT_SEC": "900",
        "DARCHIVE_PROCESSOR_BATCH_SIZE": "10",
        "DARCHIVE_TESSERACT_BIN": "tesseract",
    }
    values.update(
        {key: value.strip() for key, value in (provider_values or {}).items() if value is not None}
    )
    update_env_values(env_file, values)
    os.environ.update(values)

def ask_yes_no(prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt} {suffix} ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}

def install_launch_agent(root: Path, *, dry_run: bool) -> int:
    script = root / "scripts" / "install_launch_agent.sh"
    if dry_run:
        print(f"[dry-run] {script}")
        return 0
    if not script.exists():
        print(f"[FAIL] launchd install script missing: {script}")
        return 1
    proc = subprocess_run_script(script)
    return proc

def subprocess_run_script(script: Path) -> int:
    import subprocess

    return subprocess.run([str(script)], cwd=script.parents[1], check=False).returncode
