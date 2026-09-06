from __future__ import annotations

import json
from typing import Any

from dalife.bot_prompts import (
    create_post_process_prompt,
    create_project_seed_digest_prompt,
    create_revisit_digest_prompt,
    create_weekly_insight_prompt,
)
from dalife.cli_formatting import mask_identifier, only_allowed_chat_id
from dalife.config import Settings
from dalife.storage import ArchiveStore
from dalife.telegram import (
    DEFAULT_BOT_COMMANDS,
    REGISTERED_CHAT_BOT_COMMANDS,
    TelegramApiClient,
    chat_command_scope,
    discover_chat_candidates,
    read_room_state,
    send_bot_prompt,
)


def discover_chat_cmd(settings: Settings, plain: bool, json_output: bool) -> int:
    if not settings.telegram_bot_token:
        print("[FAIL] TELEGRAM_BOT_TOKEN is not configured")
        return 1
    payload = TelegramApiClient(settings.telegram_bot_token).get_updates()
    candidates = discover_chat_candidates(payload)
    if json_output:
        print(json.dumps([candidate.__dict__ for candidate in candidates], ensure_ascii=False, indent=2))
        return 0
    if plain:
        for candidate in candidates:
            print(candidate.chat_id)
        return 0
    if not candidates:
        print("no recent Telegram chats found")
        return 0
    for candidate in candidates:
        print(f"{mask_identifier(candidate.chat_id)}\t{candidate.chat_type}\t{candidate.title}")
    return 0

def telegram_commands_cmd(settings: Settings, action: str) -> int:
    if not settings.telegram_bot_token:
        print("[FAIL] TELEGRAM_BOT_TOKEN is not configured")
        return 1
    api = TelegramApiClient(settings.telegram_bot_token)
    state = read_room_state(settings)
    if action == "show":
        print("[default]")
        print_commands(api.get_my_commands())
        if state.dalife_chat_id:
            print(f"[registered chat {mask_identifier(state.dalife_chat_id)}]")
            print_commands(api.get_my_commands(scope=chat_command_scope(state.dalife_chat_id)))
        return 0
    if action == "sync":
        api.set_my_commands(DEFAULT_BOT_COMMANDS)
        if state.dalife_chat_id:
            api.set_my_commands(REGISTERED_CHAT_BOT_COMMANDS, scope=chat_command_scope(state.dalife_chat_id))
            print("Telegram commands synced: default and registered chat")
        else:
            print("Telegram commands synced: default")
        return 0
    return 2

def print_commands(commands: list[dict[str, str]]) -> None:
    if not commands:
        print("(empty)")
        return
    for item in commands:
        print(f"/{item.get('command', '')} - {item.get('description', '')}")

def send_test_cmd(
    settings: Settings,
    *,
    chat_id: str | None,
    use_registered: bool,
    use_allowed: bool,
    dry_run: bool,
) -> int:
    if not settings.telegram_bot_token:
        print("[FAIL] TELEGRAM_BOT_TOKEN is not configured")
        return 1
    target_count = sum(1 for value in (chat_id, use_registered, use_allowed) if bool(value))
    if target_count != 1:
        print("[FAIL] choose exactly one target: --chat-id, --registered, or --allowed")
        return 2
    target = ""
    if chat_id:
        target = chat_id
    elif use_registered:
        target = read_room_state(settings).dalife_chat_id
    elif use_allowed:
        target = only_allowed_chat_id(settings)
    if not target:
        print("[FAIL] selected target is not configured")
        return 1
    if dry_run:
        print(f"[dry-run] would send test message to {mask_identifier(target)}")
        return 0
    TelegramApiClient(settings.telegram_bot_token).send_message(target, "DaLife 테스트 메시지입니다.")
    print(f"sent test message to {mask_identifier(target)}")
    return 0

def telegram_digest_cmd_impl(
    settings: Settings,
    store: ArchiveStore,
    *,
    kind: str,
    limit: int,
    dry_run: bool,
    json_output: bool,
    api_factory: Any,
) -> int:
    chat_id = target_prompt_chat_id(settings)
    if not chat_id:
        message = "No Telegram chat is configured for proactive DaLife prompts."
        if json_output:
            print(json.dumps({"status": "skipped", "reason": message}, ensure_ascii=False, indent=2))
        else:
            print(f"[SKIP] {message}")
        return 0
    prompt = create_digest_prompt(store, chat_id=chat_id, kind=kind, limit=limit)
    if prompt is None:
        payload = {"status": "skipped", "kind": kind, "reason": "no useful prompt candidates"}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else f"[SKIP] {payload['reason']}")
        return 0
    if dry_run:
        payload = {"status": "dry-run", "kind": kind, "prompt": prompt}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else f"[dry-run] would send {prompt['title']}")
        return 0
    if not settings.telegram_bot_token:
        payload = {"status": "skipped", "kind": kind, "reason": "TELEGRAM_BOT_TOKEN is not configured", "prompt": prompt}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else f"[SKIP] {payload['reason']}")
        return 0
    result = send_bot_prompt(api_factory(settings.telegram_bot_token), store, prompt)
    payload = {"kind": kind, **result}
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload.get("status") == "sent":
        print(f"sent {kind} prompt to {mask_identifier(chat_id)}")
    else:
        print(f"[SKIP] {payload.get('reason') or 'prompt was not sent'}")
    return 0

def create_digest_prompt(store: ArchiveStore, *, chat_id: str, kind: str, limit: int) -> dict[str, Any] | None:
    if kind == "revisit":
        return create_revisit_digest_prompt(store, chat_id, limit=limit)
    if kind == "project-seed":
        return create_project_seed_digest_prompt(store, chat_id, limit=limit)
    if kind == "weekly":
        return create_weekly_insight_prompt(store, chat_id)
    return None

def send_processed_capture_prompts_impl(
    settings: Settings,
    store: ArchiveStore,
    results: list[dict[str, Any]],
    *,
    api_factory: Any,
) -> list[dict[str, Any]]:
    if not settings.telegram_bot_token:
        return []
    api = api_factory(settings.telegram_bot_token)
    sent: list[dict[str, Any]] = []
    for item in results:
        if item.get("status") != "processed":
            continue
        prompt = create_post_process_prompt(store, str(item.get("capture_id") or ""))
        if prompt is None:
            continue
        try:
            sent.append(send_bot_prompt(api, store, prompt))
        except Exception:
            # Scheduled processing should not fail only because Telegram delivery failed.
            continue
    return sent

def target_prompt_chat_id(settings: Settings) -> str:
    state = read_room_state(settings)
    if state.dalife_chat_id:
        return state.dalife_chat_id
    if len(settings.telegram_allowed_chat_ids) == 1:
        return settings.telegram_allowed_chat_ids[0]
    return ""
