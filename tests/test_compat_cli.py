from __future__ import annotations

from pathlib import Path

from darchivebot import compat_cli


def test_delegate_cli_uses_env_override(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setenv("DARCHIVE_MOMUK_CLI", "/tmp/momuk")
    monkeypatch.setattr(compat_cli, "run_command", lambda command: calls.append(command) or 0)

    assert compat_cli.delegate_cli(
        argv=["doctor"],
        env_var="DARCHIVE_MOMUK_CLI",
        candidates=(),
        python_module="momukbot.cli",
        label="momuk",
    ) == 0

    assert calls == [["/tmp/momuk", "doctor"]]


def test_delegate_cli_uses_python_module_for_python_candidate(tmp_path, monkeypatch):
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.delenv("DARCHIVE_HONSANAM_REMINDER_CLI", raising=False)
    monkeypatch.setattr(compat_cli, "run_command", lambda command: calls.append(command) or 0)

    assert compat_cli.delegate_cli(
        argv=["next", "--days", "14"],
        env_var="DARCHIVE_HONSANAM_REMINDER_CLI",
        candidates=(python,),
        python_module="life_reminder.cli",
        label="honsanam-reminder",
    ) == 0

    assert calls == [[str(python), "-m", "life_reminder.cli", "next", "--days", "14"]]


def test_delegate_cli_reports_missing_source_cli(monkeypatch, capsys):
    monkeypatch.delenv("DARCHIVE_MOMUK_CLI", raising=False)

    assert compat_cli.delegate_cli(
        argv=["doctor"],
        env_var="DARCHIVE_MOMUK_CLI",
        candidates=(Path("/not/a/real/command"),),
        python_module="momukbot.cli",
        label="momuk",
    ) == 127

    assert "DARCHIVE_MOMUK_CLI" in capsys.readouterr().err


def test_project_exposes_compatibility_console_scripts():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'momuk = "darchivebot.compat_cli:momuk_main"' in text
    assert 'honsanam-reminder = "darchivebot.compat_cli:honsanam_reminder_main"' in text


def test_honsanam_wrapper_routes_migrated_commands_to_native_cli(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_HONSANAM_REMINDER_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda argv: calls.append(argv) or 0)

    assert compat_cli.honsanam_reminder_main(["show", "trash", "--json"]) == 0

    assert calls == [["life", "show", "trash", "--json"]]


def test_honsanam_wrapper_adds_current_time_to_native_next(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_HONSANAM_REMINDER_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda argv: calls.append(argv) or 0)

    assert compat_cli.honsanam_reminder_main(["next", "--days", "3"]) == 0

    assert calls[0][:4] == ["life", "next", "--days", "3"]
    assert "--date" in calls[0]
    assert "--time" in calls[0]


def test_honsanam_wrapper_routes_setup_independent_commands_to_native_cli(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_HONSANAM_REMINDER_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda args: calls.append(args) or 0)

    assert compat_cli.honsanam_reminder_main(["init"]) == 0
    assert compat_cli.honsanam_reminder_main(["doctor"]) == 0
    assert compat_cli.honsanam_reminder_main(["discover-chat", "--json"]) == 0
    assert compat_cli.honsanam_reminder_main(["send-test"]) == 0
    assert calls == [
        ["init"],
        ["doctor", "--online"],
        ["discover-chat", "--json"],
        ["send-test", "--allowed"],
    ]

    assert compat_cli.honsanam_reminder_main(
        ["setup", "--non-interactive", "--timezone", "Asia/Seoul"]
    ) == 0
    assert calls[-1] == ["setup", "--non-interactive", "--timezone", "Asia/Seoul"]


def test_honsanam_wrapper_still_delegates_unmigrated_commands(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_HONSANAM_REMINDER_CLI", raising=False)
    monkeypatch.setattr(compat_cli, "delegate_cli", lambda **kwargs: calls.append(kwargs) or 0)

    assert compat_cli.honsanam_reminder_main(["setup", "--install-launchd", "--dry-run"]) == 0

    assert calls[0]["argv"] == ["setup", "--install-launchd", "--dry-run"]


def test_momuk_wrapper_routes_parse_and_recommend_to_native_cli(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_MOMUK_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda argv: calls.append(argv) or 0)

    assert compat_cli.momuk_main(["parse", "신정동 맛집 추천", "--json"]) == 0
    assert compat_cli.momuk_main([
        "recommend", "--area", "신정동", "--topic", "한식", "--count", "5", "--dry-run",
    ]) == 0

    assert calls[0] == ["food", "parse", "신정동 맛집 추천", "--json"]
    assert calls[1] == [
        "food", "recommend-local", "--area", "신정동", "--topic", "한식",
        "--count", "5", "--dry-run",
    ]


def test_momuk_wrapper_routes_shared_operational_commands_natively(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_MOMUK_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda args: calls.append(args) or 0)

    commands = [
        (["init"], ["init"]),
        (["doctor"], ["doctor", "--online"]),
        (["rooms"], ["rooms"]),
        (["discover-chat", "--json"], ["discover-chat", "--json"]),
        (["send-test", "--allowed", "--dry-run"], ["send-test", "--allowed", "--dry-run"]),
        (["telegram-commands", "show"], ["telegram-commands", "show"]),
        (["quota"], ["food", "quota"]),
        (
            ["setup", "--non-interactive", "--kakao-rest-api-key", "secret"],
            ["setup", "--non-interactive", "--kakao-rest-api-key", "secret"],
        ),
    ]
    for legacy, native in commands:
        assert compat_cli.momuk_main(legacy) == 0
        assert calls[-1] == native


def test_momuk_wrapper_translates_natural_recommendation(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_MOMUK_CLI", raising=False)
    monkeypatch.setattr("darchivebot.cli.main", lambda argv: calls.append(argv) or 0)

    assert compat_cli.momuk_main(["recommend", "이태원에서 저녁 맛집 3곳 추천", "--dry-run"]) == 0

    assert calls[0][:4] == ["food", "recommend-local", "--area", "이태원"]
    assert calls[0][-1] == "--dry-run"


def test_momuk_wrapper_keeps_unmigrated_commands_and_help_delegated(monkeypatch):
    calls = []
    monkeypatch.delenv("DARCHIVE_MOMUK_CLI", raising=False)
    monkeypatch.setattr(compat_cli, "delegate_cli", lambda **kwargs: calls.append(kwargs) or 0)

    assert compat_cli.momuk_main(["events"]) == 0
    assert compat_cli.momuk_main(["recommend", "--help"]) == 0

    assert [call["argv"] for call in calls] == [["events"], ["recommend", "--help"]]
