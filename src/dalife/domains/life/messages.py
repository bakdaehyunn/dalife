from __future__ import annotations

from dalife.domains.life.patterns import MessagePattern


def card(title: str, schedule: str, action: str, note: str = "", pattern: MessagePattern | None = None) -> str:
    pattern = pattern or MessagePattern()
    parts = [
        f"{pattern.prefix} | {title}",
        "",
        pattern.schedule_label,
        schedule,
        "",
        pattern.action_label,
        action,
    ]
    if note:
        parts.extend(["", pattern.note_label, note])
    return "\n".join(parts)

