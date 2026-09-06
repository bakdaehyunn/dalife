from __future__ import annotations

from dataclasses import asdict, dataclass

from dalife.ports import PersonalContextRepositoryPort


LIFE_MESSAGE_PATTERN_KEY = "life.message_pattern"


@dataclass(frozen=True)
class MessagePattern:
    prefix: str = "생활알림"
    schedule_label: str = "언제"
    action_label: str = "해야 할 일"
    note_label: str = "관리 포인트"


def load_message_pattern(store: PersonalContextRepositoryPort) -> MessagePattern:
    values = store.get_app_setting(setting_key=LIFE_MESSAGE_PATTERN_KEY) or {}
    default = MessagePattern()
    return MessagePattern(
        prefix=str(values.get("prefix") or default.prefix),
        schedule_label=str(values.get("schedule_label") or default.schedule_label),
        action_label=str(values.get("action_label") or default.action_label),
        note_label=str(values.get("note_label") or default.note_label),
    )


def update_message_pattern(
    store: PersonalContextRepositoryPort,
    **values: str | None,
) -> MessagePattern:
    current = load_message_pattern(store)
    updated = MessagePattern(
        prefix=_value(values.get("prefix"), current.prefix),
        schedule_label=_value(values.get("schedule_label"), current.schedule_label),
        action_label=_value(values.get("action_label"), current.action_label),
        note_label=_value(values.get("note_label"), current.note_label),
    )
    store.set_app_setting(setting_key=LIFE_MESSAGE_PATTERN_KEY, value=asdict(updated))
    return updated


def _value(value: str | None, current: str) -> str:
    if value is None:
        return current
    stripped = value.strip()
    if not stripped:
        raise ValueError("message pattern values must not be empty")
    return stripped
