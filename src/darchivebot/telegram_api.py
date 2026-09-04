from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from darchivebot.json_utils import dumps


class TelegramApiClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def get_me(self) -> dict[str, Any]:
        return self._api("getMe")

    def get_updates(
        self,
        offset: int | None = None,
        timeout: int | None = None,
        limit: int | None = 100,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {}
        if offset is not None:
            params["offset"] = offset
        if timeout is not None:
            params["timeout"] = timeout
        if limit is not None:
            params["limit"] = limit
        request_timeout = (timeout + 5) if timeout is not None else 15
        return self._api("getUpdates", params, request_timeout=request_timeout)

    def get_file(self, file_id: str) -> dict[str, Any]:
        payload = self._api("getFile", {"file_id": file_id})
        result = payload.get("result")
        return result if isinstance(result, dict) else {}

    def send_message(self, chat_id: str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
        if reply_markup is not None:
            params["reply_markup"] = dumps(reply_markup)
        return self._api(
            "sendMessage",
            params,
            method="POST",
        )

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> None:
        params = {"callback_query_id": callback_query_id}
        if text:
            params["text"] = text
        self._api("answerCallbackQuery", params, method="POST")

    def edit_message_reply_markup(
        self,
        chat_id: str,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        params: dict[str, str | int] = {"chat_id": chat_id, "message_id": message_id}
        params["reply_markup"] = dumps(reply_markup or {"inline_keyboard": []})
        self._api("editMessageReplyMarkup", params, method="POST")

    def get_my_commands(self, scope: dict[str, str] | None = None) -> list[dict[str, str]]:
        params: dict[str, str] = {}
        if scope is not None:
            params["scope"] = dumps(scope)
        payload = self._api("getMyCommands", params)
        result = payload.get("result")
        if not isinstance(result, list):
            return []
        commands: list[dict[str, str]] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            commands.append(
                {
                    "command": str(item.get("command") or ""),
                    "description": str(item.get("description") or ""),
                }
            )
        return commands

    def set_my_commands(self, commands: list[dict[str, str]], scope: dict[str, str] | None = None) -> None:
        params = {"commands": dumps(commands)}
        if scope is not None:
            params["scope"] = dumps(scope)
        self._api("setMyCommands", params, method="POST")

    def download_file(self, file_path: str, destination: Path) -> None:
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        req = Request(url, method="GET")
        with urlopen(req, timeout=30) as resp:
            destination.write_bytes(resp.read())

    def _api(
        self,
        method_name: str,
        params: dict[str, str | int] | None = None,
        method: str = "GET",
        request_timeout: int = 15,
    ) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        params = params or {}
        url = f"https://api.telegram.org/bot{self.token}/{method_name}"
        data = None
        if method == "GET":
            if params:
                url = f"{url}?{urlencode(params)}"
        else:
            data = urlencode(params).encode("utf-8")
        req = Request(url, data=data, method=method)
        with urlopen(req, timeout=request_timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError(f"Telegram API failed: {payload}")
        return payload
