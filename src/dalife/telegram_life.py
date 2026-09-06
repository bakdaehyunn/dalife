from __future__ import annotations

from datetime import datetime

from dalife.domains.life import life_config_from_store, load_message_pattern, upcoming_reminders
from dalife.ports import PersonalContextRepositoryPort


def upcoming_life_for_telegram(
    store: PersonalContextRepositoryPort,
    text: str,
    *,
    now: datetime,
    days: int = 7,
) -> str:
    reminders = upcoming_reminders(
        now,
        life_config_from_store(store),
        days=days,
        pattern=load_message_pattern(store),
    )
    matched = [item for item in reminders if _matches(item.title, item.reminder_id, text)]
    selected = matched or reminders
    if not selected:
        return f"앞으로 {days}일 안에 예정된 생활 알림이 없어요."
    lines = [f"앞으로 {days}일 생활 알림", ""]
    for item in selected[:10]:
        lines.append(f"- {item.scheduled_at:%m월 %d일 %H:%M} · {item.title}")
    return "\n".join(lines)


def _matches(title: str, reminder_id: str, text: str) -> bool:
    compact = text.replace(" ", "").lower()
    candidates = (title.replace(" ", "").lower(), reminder_id.replace("-", "").lower())
    return any(candidate and candidate in compact for candidate in candidates)
