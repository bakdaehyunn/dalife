from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_covers_private_runtime_files():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
    assert ".local/" in text
    assert "*.sqlite3" in text
    assert "*.log" in text


def test_launchd_scripts_reference_bot_and_processor():
    install = (ROOT / "scripts" / "install_launch_agent.sh").read_text(encoding="utf-8")
    launchd = (ROOT / "src" / "dalife" / "launchd.py").read_text(encoding="utf-8")
    assert "python\" -m dalife.launchd install" in install
    assert "launchd_schedule" in launchd
    assert "com.hennei.dalife.telegram" in launchd
    assert "com.hennei.dalife.processor" in launchd
    assert "com.hennei.dalife.food-collect" in launchd
    assert "com.hennei.dalife.life-send" in launchd
    assert '"telegram"' in launchd
    assert "ProgramArguments" in launchd
    assert "job.command" in launchd
    assert "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" in launchd


def test_preflight_script_checks_private_runtime_files_and_secrets():
    preflight = (ROOT / "scripts" / "preflight_public.sh").read_text(encoding="utf-8")
    assert "git ls-files --error-unmatch .env" in preflight
    assert "*.sqlite3" in preflight
    assert "TELEGRAM_BOT_TOKEN" in preflight


def test_readme_documents_the_pruned_personal_assistant_surface():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Telegram-first personal assistant" in text
    assert "SQLite is the source of truth" in text
    assert "four jobs" in text
    assert "graph database" in text
    assert "dalife archive list" in text
    assert "dalife food parse" in text
    assert "dalife food plan-collection" in text
    assert "dalife life run-once" in text
    assert "dalife course plan" in text
    assert "dalife life list" in text
    assert "dalife life next" in text
    assert "dalife life preview" in text
    assert "dalife course plan" in text
    assert "dalife schedule plan" in text
    assert "MVP" not in text


def test_source_migration_docs_capture_final_dalife_command_surface():
    momuk = (ROOT / "docs" / "migrations" / "momukbot.md").read_text(encoding="utf-8")
    honsanam = (ROOT / "docs" / "migrations" / "honsanam-reminder-bot.md").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "Target domain: `dalife.domains.food`" in momuk
    assert "momuk recommend" in momuk
    assert "momuk telegram" in momuk
    assert "KAKAO_REST_API_KEY" in momuk
    assert "NAVER_DAILY_SOFT_LIMIT" in momuk
    assert "has uncommitted recommendation-quality work" in momuk
    assert "temporary `momuk` compatibility executable has been removed" in momuk

    assert "Target domain: `dalife.domains.life`" in honsanam
    assert "honsanam-reminder run-once" in honsanam
    assert "honsanam-reminder poll-replies --watch" in honsanam
    assert "TELEGRAM_REMINDER_CHAT_ID" in honsanam
    assert "stale" in honsanam
    assert "temporary `honsanam-reminder` compatibility executable has been removed" in honsanam

    assert 'dalife = "dalife.cli:main"' in pyproject
    assert "compat_cli" not in pyproject
