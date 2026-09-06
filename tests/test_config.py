from __future__ import annotations

import os

from dalife.config import get_settings, read_env_values, resolve_executable, update_env_values


def test_resolve_executable_uses_extra_dirs_when_path_is_minimal(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "codex"
    executable.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    assert resolve_executable("codex", extra_dirs=(bin_dir,)) == str(executable)


def test_resolve_executable_preserves_explicit_paths(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    assert resolve_executable(str(executable)) == str(executable)


def test_resolve_executable_falls_back_to_original_value(monkeypatch):
    monkeypatch.setenv("PATH", os.devnull)

    assert resolve_executable("not-a-real-dalife-command", extra_dirs=()) == "not-a-real-dalife-command"


def test_update_env_values_preserves_comments_and_unrelated_provider_settings(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local settings\nTELEGRAM_BOT_TOKEN=old\nKAKAO_REST_API_KEY=keep-me\n",
        encoding="utf-8",
    )

    update_env_values(env_file, {"TELEGRAM_BOT_TOKEN": "new", "NAVER_CLIENT_ID": "client"})

    text = env_file.read_text(encoding="utf-8")
    assert "# local settings" in text
    assert "KAKAO_REST_API_KEY=keep-me" in text
    assert read_env_values(env_file)["TELEGRAM_BOT_TOKEN"] == "new"
    assert read_env_values(env_file)["NAVER_CLIENT_ID"] == "client"


def test_native_personal_telegram_is_off_by_default_and_explicitly_enabled(monkeypatch, tmp_path):
    monkeypatch.delenv("DALIFE_NATIVE_PERSONAL_TELEGRAM", raising=False)
    assert get_settings(tmp_path).native_personal_telegram_enabled is False

    monkeypatch.setenv("DALIFE_NATIVE_PERSONAL_TELEGRAM", "true")
    assert get_settings(tmp_path).native_personal_telegram_enabled is True


def test_life_timezone_defaults_to_seoul_and_can_be_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("DALIFE_LIFE_TIMEZONE", raising=False)
    assert get_settings(tmp_path).life_timezone == "Asia/Seoul"

    monkeypatch.setenv("DALIFE_LIFE_TIMEZONE", "America/New_York")
    assert get_settings(tmp_path).life_timezone == "America/New_York"
