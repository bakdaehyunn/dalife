from __future__ import annotations

from dataclasses import dataclass
from typing import Any


InteractionLabels = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FixedReminderSpec:
    reminder_id: str
    config_section: str
    schedule_kind: str
    title: str
    default_action: str
    default_note: str
    editable_fields: frozenset[str]
    interaction_labels: InteractionLabels
    section_prefix: str | None = None
    extra_effective_keys: tuple[str, ...] = ()
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None
    followup_days: int | None = None


COMMON_TEXT_FIELDS = frozenset({"enabled", "title", "action", "note", "time"})
INTERVAL_FIELDS = COMMON_TEXT_FIELDS | {"base_date", "days"}


FIXED_REMINDERS: dict[str, FixedReminderSpec] = {
    "haircut": FixedReminderSpec(
        reminder_id="haircut",
        config_section="haircut",
        schedule_kind="haircut",
        title="미용실 예약",
        default_action="오늘 미용실 예약하기",
        default_note="이번 주 가능한 시간 먼저 확인하기\n머리만 정리해도 인상이 꽤 달라집니다.",
        editable_fields=frozenset(
            {
                "enabled",
                "title",
                "action",
                "note",
                "time",
                "base_date",
                "requires_confirmation",
                "confirmation_prompt",
                "followup_days",
            }
        ),
        interaction_labels=(("예약했음", "yes"), ("아직", "no")),
        extra_effective_keys=("base_date", "requires_confirmation", "confirmation_prompt", "followup_days"),
        requires_confirmation=True,
        confirmation_prompt="미용실 예약했나요?",
        followup_days=7,
    ),
    "fingernails": FixedReminderSpec(
        "fingernails",
        "nails",
        "nails",
        "손톱 관리",
        "손톱 자르기",
        "손톱 끝만 깔끔하게 정리하기\n손 볼 때 생각보다 티 납니다.",
        frozenset(INTERVAL_FIELDS),
        (("정리했음", "done"), ("나중에", "later")),
        section_prefix="fingernails",
    ),
    "toenails": FixedReminderSpec(
        "toenails",
        "nails",
        "nails",
        "발톱 관리",
        "발톱 자르기",
        "길어지기 전에 미리 정리하기\n양말 신을 때 거슬리기 전에 정리해 주세요.",
        frozenset(INTERVAL_FIELDS),
        (("정리했음", "done"), ("나중에", "later")),
        section_prefix="toenails",
    ),
    "nose-hair": FixedReminderSpec(
        "nose-hair",
        "nose_hair",
        "interval",
        "코털 정리",
        "코털 정리하기",
        "거울 보고 삐져나온 것만 정리하기\n말할 때 은근히 먼저 보입니다.",
        frozenset(INTERVAL_FIELDS),
        (("정리했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
    "eyebrows": FixedReminderSpec(
        "eyebrows",
        "eyebrows",
        "interval",
        "눈썹 정리",
        "눈썹 정리하기",
        "삐져나온 눈썹만 가볍게 정리하기\n눈썹 라인만 정리해도 얼굴이 깔끔해 보입니다.",
        frozenset(INTERVAL_FIELDS),
        (("정리했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
    "earwax": FixedReminderSpec(
        "earwax",
        "earwax",
        "interval",
        "귀지 정리",
        "귀 주변 정리하기",
        "면봉으로 깊게 파지 말고 겉만 정리하기\n이어폰 쓸 때 생각보다 신경 쓰입니다.",
        frozenset(INTERVAL_FIELDS),
        (("정리했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
    "toothbrush": FixedReminderSpec(
        "toothbrush",
        "toothbrush",
        "interval",
        "칫솔 교체",
        "칫솔 교체하기",
        "칫솔모 벌어진 정도 확인하기\n한 달에 한 번 바꾸면 양치감이 달라집니다.",
        frozenset(INTERVAL_FIELDS),
        (("교체했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
    "trash": FixedReminderSpec(
        "trash",
        "trash",
        "trash",
        "분리수거",
        "오늘 분리수거 내놓기",
        "오늘 23:00쯤 수거 예정입니다.\n종량제 봉투와 음식물 봉투 여유분도 확인해 주세요.\n재활용품은 비우고 헹구면 뒤처리가 편합니다.",
        frozenset(COMMON_TEXT_FIELDS),
        (("내놨음", "done"), ("나중에", "later")),
        extra_effective_keys=("weekdays",),
    ),
    "mac-status": FixedReminderSpec(
        "mac-status",
        "mac_status",
        "weekly",
        "맥북 상태점검",
        "맥북 상태 확인",
        "배터리, 저장공간, 업데이트 상태 확인하기\n오래 켜져 있으면 재부팅 한 번 해 주세요.",
        frozenset(COMMON_TEXT_FIELDS | {"weekday"}),
        (("확인했음", "checked"),),
        extra_effective_keys=("weekday",),
    ),
    "weekend-cleaning": FixedReminderSpec(
        "weekend-cleaning",
        "cleaning",
        "weekly",
        "주말 청소",
        "주말 청소 루틴 진행하기",
        "바닥, 책상, 설거지, 쓰레기부터 정리하기\n집이 정리되면 주말이 덜 밀립니다.",
        frozenset(COMMON_TEXT_FIELDS | {"weekday"}),
        (("청소했음", "done"), ("나중에", "later")),
        extra_effective_keys=("weekday",),
    ),
    "bedding-wash": FixedReminderSpec(
        "bedding-wash",
        "bedding",
        "interval",
        "이불 빨래",
        "이불 빨래하기",
        "이불 커버와 베개 커버도 같이 확인하기\n잠자리가 산뜻하면 잠도 편합니다.",
        frozenset(INTERVAL_FIELDS),
        (("빨래했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
    "bathroom-cleaning": FixedReminderSpec(
        "bathroom-cleaning",
        "bathroom",
        "interval",
        "화장실 청소",
        "화장실 청소하기",
        "변기, 세면대, 배수구부터 정리하기\n화장실은 미루면 바로 티 납니다.",
        frozenset(INTERVAL_FIELDS),
        (("청소했음", "done"), ("나중에", "later")),
        extra_effective_keys=("base_date", "days"),
    ),
}


FIXED_REMINDER_ORDER = (
    "haircut",
    "fingernails",
    "toenails",
    "trash",
    "mac-status",
    "weekend-cleaning",
    "bedding-wash",
    "bathroom-cleaning",
    "nose-hair",
    "eyebrows",
    "earwax",
    "toothbrush",
)


def get_fixed_spec(reminder_id: str) -> FixedReminderSpec:
    return FIXED_REMINDERS[reminder_id]


def fixed_spec_for_scheduled_id(reminder_id: str) -> FixedReminderSpec | None:
    if reminder_id.startswith("haircut-booking-"):
        return FIXED_REMINDERS["haircut"]
    for fixed_id in FIXED_REMINDER_ORDER:
        if reminder_id == fixed_id or reminder_id.startswith(f"{fixed_id}-"):
            return FIXED_REMINDERS[fixed_id]
    return None


def fixed_specs_by_kind(schedule_kind: str) -> list[FixedReminderSpec]:
    return [FIXED_REMINDERS[reminder_id] for reminder_id in FIXED_REMINDER_ORDER if FIXED_REMINDERS[reminder_id].schedule_kind == schedule_kind]


def default_reminder_sections() -> list[tuple[str, dict[str, Any]]]:
    return [
        ("haircut", {"enabled": True, "base_date": "2026-05-10", "interval_months": 1, "notify_time": "08:45", "weekend_policy": "previous_sunday", "requires_confirmation": True, "confirmation_prompt": FIXED_REMINDERS["haircut"].confirmation_prompt, "followup_days": FIXED_REMINDERS["haircut"].followup_days}),
        ("nails", {"enabled": True, "base_date": "2026-05-13", "fingernails_days": 7, "toenails_days": 21, "notify_time": "21:00"}),
        ("trash", {"enabled": True, "weekdays": ["tue", "thu", "sun"], "notify_time": "20:00", "note": FIXED_REMINDERS["trash"].default_note}),
        ("mac_status", {"enabled": True, "weekday": "sat", "notify_time": "10:00"}),
        ("cleaning", {"enabled": True, "weekday": "sat", "notify_time": "14:00", "note": FIXED_REMINDERS["weekend-cleaning"].default_note}),
        ("bedding", {"enabled": True, "base_date": "2026-05-24", "days": 14, "notify_time": "14:00", "note": FIXED_REMINDERS["bedding-wash"].default_note}),
        ("bathroom", {"enabled": True, "base_date": "2026-05-17", "days": 14, "notify_time": "10:30", "note": FIXED_REMINDERS["bathroom-cleaning"].default_note}),
        ("nose_hair", {"enabled": True, "base_date": "2026-05-22", "days": 14, "notify_time": "20:30", "note": FIXED_REMINDERS["nose-hair"].default_note}),
        ("eyebrows", {"enabled": True, "base_date": "2026-05-22", "days": 14, "notify_time": "20:40", "note": FIXED_REMINDERS["eyebrows"].default_note}),
        ("earwax", {"enabled": True, "base_date": "2026-05-25", "days": 21, "notify_time": "21:00", "note": FIXED_REMINDERS["earwax"].default_note}),
        ("toothbrush", {"enabled": True, "base_date": "2026-05-29", "days": 30, "notify_time": "21:30", "note": FIXED_REMINDERS["toothbrush"].default_note}),
    ]


def default_reminder_config() -> dict[str, Any]:
    return {section: values for section, values in default_reminder_sections()}
