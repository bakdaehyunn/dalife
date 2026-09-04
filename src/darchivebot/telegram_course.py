from __future__ import annotations

from datetime import datetime

from darchivebot.domains.course import match_course_area, plan_local_course
from darchivebot.ports import TelegramStore


def plan_course_for_telegram(
    store: TelegramStore,
    text: str,
    *,
    now: datetime,
) -> str:
    area = match_course_area(store, text)
    if area is None:
        return "코스를 만들 지역 이름을 함께 알려주세요."
    area_name = str(area["name"])
    result = plan_local_course(
        store,
        title=f"{area_name} 코스",
        area_name=area_name,
        generated_at=now,
        intent=text,
        persist=True,
    )
    if not result.plan.stops:
        return f"{area_name}에서 코스로 묶을 저장 데이터가 아직 부족해요."
    lines = [f"{result.plan.title}", ""]
    for index, stop in enumerate(result.plan.stops, start=1):
        lines.append(f"{index}. {stop.title}")
        lines.append(f"   {stop.reason}")
    if result.stored is not None:
        lines.extend(["", f"plan_id: {result.stored['id']}"])
    return "\n".join(lines)
