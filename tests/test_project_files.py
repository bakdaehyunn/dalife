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
    assert "com.hennei.dalife.digest" in launchd
    assert "com.hennei.dalife.digest.project-seed" in launchd
    assert "com.hennei.dalife.digest.weekly" in launchd
    assert '"telegram"' in launchd
    assert "ProgramArguments" in launchd
    assert "job.command" in launchd
    assert "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" in launchd


def test_preflight_script_checks_private_runtime_files_and_secrets():
    preflight = (ROOT / "scripts" / "preflight_public.sh").read_text(encoding="utf-8")
    assert "git ls-files --error-unmatch .env" in preflight
    assert "*.sqlite3" in preflight
    assert "TELEGRAM_BOT_TOKEN" in preflight


def test_readme_frames_product_as_interest_aware_archive_without_mvp_language():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "아이디어 주머니" in text
    assert "AI, 커리어, 테크놀로지, 스포츠 같은 관심사" in text
    assert "Momukbot의 맛집 추천 도메인" in text
    assert "Honsanam Reminder의 생활 알림 도메인" in text
    assert "canonical repo" in text
    assert "SQLite가 운영 데이터의 source of truth" in text
    assert "`archive`" in text
    assert "`food`" in text
    assert "`life`" in text
    assert "`course`" in text
    assert "momuk" in text
    assert "honsanam-reminder" in text
    assert "dalife archive list" in text
    assert "dalife food parse" in text
    assert "dalife food plan-collection" in text
    assert "dalife life list" in text
    assert "dalife life next" in text
    assert "dalife life preview" in text
    assert "dalife course plan" in text
    assert "dalife schedule plan" in text
    assert "Viewpoint Layer" in text
    assert "insight seed" in text
    assert "dalife insights generate --period weekly" in text
    assert "failed_blocked" in text
    assert "archive interpretation history" in text
    assert "docs/viewpoint-layer.md" in text
    assert "docs/ontology-graph.md" in text
    assert "MVP" not in text


def test_viewpoint_layer_docs_define_final_product_layer():
    text = (ROOT / "docs" / "viewpoint-layer.md").read_text(encoding="utf-8")
    assert "The Viewpoint Layer is the long-term product layer" in text
    assert "Capture Layer" in text
    assert "Archive Layer" in text
    assert "Semantic Graph Layer" in text
    assert "Viewpoint Layer" in text
    assert "SQLite remains the operational source of truth" in text
    assert "Raw text is excluded from normal graph and viewpoint outputs" in text
    assert "add `dalife graph quality`" in text
    assert "dalife reprocess --capture-id <capture-id>" in text
    assert "interpretation history" in text
    assert "actual archive rewrites should remain a separate" not in text


def test_ontology_graph_docs_define_semantic_store_with_lightweight_jsonld_export():
    text = (ROOT / "docs" / "ontology-graph.md").read_text(encoding="utf-8")
    assert ".local/graph/dalife.jsonld" in text
    assert ".local/graph/semantic-store/" in text
    assert "lightweight portable export" in text
    assert "not a complete backup of every RDF fact" in text
    assert "darch:Capture" in text
    assert "darch:ArchiveItem" in text
    assert "darch:hasInterest" in text
    assert "SQLite remains the source of truth" in text
    assert "raw extracted text is not exported or stored in the semantic graph by default" in text
    assert "Questions and relation candidates are stored as normalized archive fields" in text
    assert "archive_interpretations" in text


def test_personal_context_platform_docs_define_canonical_migration_boundaries():
    text = (ROOT / "docs" / "personal-context-platform.md").read_text(encoding="utf-8")
    assert "DaLife becomes the canonical repository" in text
    assert "SQLite remains the operational source of truth" in text
    assert "`archive`" in text
    assert "`food`" in text
    assert "`life`" in text
    assert "`course`" in text
    assert "derived search index and graph exports" in text
    assert "Do not use git subtree or repository archiving as the first step" in text
    assert "dalife archive" in text
    assert "dalife schedule plan" in text


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
