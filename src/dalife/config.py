from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / ".env"


def load_env(path: Path | None = None) -> None:
    env_path = path or Path(os.environ.get("DALIFE_ENV_FILE", DEFAULT_ENV_FILE))
    for key, value in read_env_values(env_path).items():
        if key not in os.environ:
            os.environ[key] = value


def read_env_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def update_env_values(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    updated_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else ""
        if key in remaining:
            updated_lines.append(f"{key}={remaining.pop(key)}")
        else:
            updated_lines.append(line)
    if remaining and updated_lines and updated_lines[-1].strip():
        updated_lines.append("")
    updated_lines.extend(f"{key}={value}" for key, value in remaining.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def env_tuple(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in env_str(name).split(",") if item.strip())


def resolve_path(raw: str, default: str, root: Path = ROOT) -> Path:
    value = raw or default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def resolve_executable(raw: str, default: str = "", extra_dirs: tuple[Path, ...] | None = None) -> str:
    value = (raw or default).strip()
    if not value:
        return ""
    expanded = Path(value).expanduser()
    if expanded.parent != Path("."):
        return str(expanded)
    found = shutil.which(value)
    if found:
        return found
    search_dirs = extra_dirs or (
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
    )
    for directory in search_dirs:
        candidate = directory / value
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return value


@dataclass(frozen=True)
class Settings:
    root: Path
    telegram_bot_token: str
    telegram_allowed_chat_ids: tuple[str, ...]
    telegram_admin_user_ids: tuple[str, ...]
    telegram_allow_all_chats: bool
    state_dir: Path
    log_dir: Path
    media_dir: Path
    codex_enabled: bool
    codex_bin: str
    codex_model: str
    codex_sandbox: str
    codex_ephemeral: bool
    codex_timeout_sec: int
    processor_batch_size: int
    tesseract_bin: str
    kakao_rest_api_key: str = ""
    kakao_daily_soft_limit: int = 1000
    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_daily_soft_limit: int = 100
    food_blog_allowed_domains: tuple[str, ...] = ("blog.naver.com",)
    native_personal_telegram_enabled: bool = False
    life_timezone: str = "Asia/Seoul"


def get_settings(root: Path = ROOT) -> Settings:
    return Settings(
        root=root,
        telegram_bot_token=env_str("TELEGRAM_BOT_TOKEN"),
        telegram_allowed_chat_ids=env_tuple("TELEGRAM_ALLOWED_CHAT_IDS"),
        telegram_admin_user_ids=env_tuple("TELEGRAM_ADMIN_USER_IDS"),
        telegram_allow_all_chats=env_bool("DALIFE_ALLOW_ALL_CHATS", False),
        state_dir=resolve_path(env_str("DALIFE_STATE_DIR"), ".local/state", root),
        log_dir=resolve_path(env_str("DALIFE_LOG_DIR"), ".local/logs", root),
        media_dir=resolve_path(env_str("DALIFE_MEDIA_DIR"), ".local/captures", root),
        codex_enabled=env_bool("DALIFE_CODEX_ENABLED", True),
        codex_bin=resolve_executable(env_str("DALIFE_CODEX_BIN"), "codex"),
        codex_model=env_str("DALIFE_CODEX_MODEL"),
        codex_sandbox=env_str("DALIFE_CODEX_SANDBOX", "read-only"),
        codex_ephemeral=env_bool("DALIFE_CODEX_EPHEMERAL", True),
        codex_timeout_sec=env_int("DALIFE_CODEX_TIMEOUT_SEC", 900),
        processor_batch_size=max(1, env_int("DALIFE_PROCESSOR_BATCH_SIZE", 10)),
        tesseract_bin=env_str("DALIFE_TESSERACT_BIN", "tesseract"),
        kakao_rest_api_key=env_str("KAKAO_REST_API_KEY"),
        kakao_daily_soft_limit=max(0, env_int("DALIFE_KAKAO_DAILY_SOFT_LIMIT", 1000)),
        naver_client_id=env_str("NAVER_CLIENT_ID"),
        naver_client_secret=env_str("NAVER_CLIENT_SECRET"),
        naver_daily_soft_limit=max(0, env_int("DALIFE_NAVER_DAILY_SOFT_LIMIT", 100)),
        food_blog_allowed_domains=tuple(
            domain.lower()
            for domain in env_tuple("DALIFE_FOOD_BLOG_ALLOWED_DOMAINS")
            if domain.lower() != "tistory.com" and not domain.lower().endswith(".tistory.com")
        )
        or ("blog.naver.com",),
        native_personal_telegram_enabled=env_bool("DALIFE_NATIVE_PERSONAL_TELEGRAM", False),
        life_timezone=env_str("DALIFE_LIFE_TIMEZONE", "Asia/Seoul"),
    )


def ensure_local_dirs(settings: Settings) -> None:
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
