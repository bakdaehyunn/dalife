from __future__ import annotations

import json
from typing import Any

from dalife.ports import TelegramStore
from dalife.telegram_api import TelegramApiClient


def send_bot_prompt(api: TelegramApiClient, store: TelegramStore, prompt: dict[str, Any]) -> dict[str, Any]:
    if str(prompt.get("status") or "pending") != "pending":
        return {
            "prompt_id": str(prompt["id"]),
            "chat_id": str(prompt["chat_id"]),
            "message_id": str(prompt.get("telegram_message_id") or ""),
            "status": "skipped",
            "reason": f"prompt is already {prompt.get('status')}",
        }
    text = format_prompt_message(prompt)
    reply_markup = inline_keyboard_for_prompt(prompt)
    payload = api.send_message(str(prompt["chat_id"]), text, reply_markup=reply_markup)
    message_id = ""
    result = payload.get("result") if isinstance(payload, dict) else None
    if isinstance(result, dict):
        message_id = str(result.get("message_id") or "")
    store.mark_bot_prompt_sent(str(prompt["id"]), telegram_message_id=message_id)
    return {"prompt_id": str(prompt["id"]), "chat_id": str(prompt["chat_id"]), "message_id": message_id, "status": "sent"}

def format_prompt_message(prompt: dict[str, Any]) -> str:
    parts = [
        str(prompt.get("title") or "DaLife prompt"),
        "",
        str(prompt.get("body") or ""),
    ]
    recommended = str(prompt.get("recommended_action") or "").strip()
    if recommended:
        parts.extend(["", recommended])
    return "\n".join(parts).strip()[:3500]

def inline_keyboard_for_prompt(prompt: dict[str, Any]) -> dict[str, Any]:
    buttons = []
    for choice in prompt.get("choices") or []:
        choice_id = str(choice.get("choice") or "")
        label = str(choice.get("label") or choice_id)
        if not choice_id:
            continue
        buttons.append({"text": label, "callback_data": prompt_callback_data(str(prompt["id"]), choice_id)})
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return {"inline_keyboard": rows}

def prompt_callback_data(prompt_id: str, choice: str) -> str:
    return f"dai:{prompt_id}:{choice}"[:64]

def parse_prompt_callback_data(value: str) -> tuple[str, str] | None:
    if not value.startswith("dai:"):
        return None
    parts = value.split(":", 2)
    if len(parts) != 3 or not parts[1] or not parts[2]:
        return None
    return parts[1], parts[2]

def prompt_choices(prompt: Any) -> list[dict[str, str]]:
    raw = prompt["choices_json"] if hasattr(prompt, "keys") and "choices_json" in prompt.keys() else "[]"
    try:
        payload = json.loads(str(raw or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [
        {"choice": str(item.get("choice") or ""), "label": str(item.get("label") or "")}
        for item in payload
        if isinstance(item, dict) and str(item.get("choice") or "").strip()
    ]

def choice_label(choices: list[dict[str, str]], choice: str) -> str:
    for item in choices:
        if item["choice"] == choice:
            return item["label"] or choice
    return choice
