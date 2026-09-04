from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from darchivebot.domains.food import (
    FOOD_FEEDBACK_CHOICES,
    FoodFeedback,
    FoodFeedbackAction,
    FoodRecommendationContext,
    parse_food_request,
    recommend_local_food,
    record_food_feedback,
)
from darchivebot.ports import PersonalContextRepositoryPort


@dataclass(frozen=True)
class FoodTelegramMessage:
    text: str
    reply_markup: dict[str, Any] | None = None


@dataclass(frozen=True)
class FoodTelegramResult:
    messages: tuple[FoodTelegramMessage, ...]
    session_id: str = ""
    returned_count: int = 0


@dataclass(frozen=True)
class FoodFeedbackCallback:
    session_id: str
    rank: int
    action: FoodFeedbackAction


def recommend_food_for_telegram(
    store: PersonalContextRepositoryPort,
    text: str,
) -> FoodTelegramResult:
    request = parse_food_request(text, default_count=10)
    if request.intent == "needs_location" or not request.area:
        return FoodTelegramResult((FoodTelegramMessage("추천할 동네나 역 이름을 함께 알려주세요."),))
    result = recommend_local_food(
        store,
        request_text=text,
        context=FoodRecommendationContext(
            area=request.area,
            topic=request.topic,
            count=request.count,
            occasion=request.occasion,
        ),
    )
    if result.area is None:
        return FoodTelegramResult(
            (FoodTelegramMessage(f"{request.area}에 저장된 장소 데이터가 아직 없어요."),)
        )
    if not result.ranked_places:
        return FoodTelegramResult(
            (FoodTelegramMessage(f"{request.area}에서 현재 추천할 후보를 찾지 못했어요."),),
            session_id=result.session_id,
        )

    messages: list[FoodTelegramMessage] = []
    ranked = list(result.ranked_places)
    for start in range(0, len(ranked), 8):
        chunk = ranked[start : start + 8]
        lines = [
            f"{request.area} 맛집 추천 {start + 1}-{start + len(chunk)} / {len(ranked)}",
            "",
        ]
        for offset, item in enumerate(chunk, start=start + 1):
            place = item.place
            lines.append(f"{offset}. {place.name} · {place.category or '분류 없음'}")
            if place.address:
                lines.append(f"   {place.address}")
            if place.map_url:
                lines.append(f"   {place.map_url}")
            lines.append(f"   근거: {_tier_label(place.evidence_tier.value)}")
        markup = _feedback_keyboard(result.session_id, start + 1, len(chunk)) if start == 0 else None
        messages.append(FoodTelegramMessage("\n".join(lines), markup))
    return FoodTelegramResult(
        tuple(messages),
        session_id=result.session_id,
        returned_count=len(ranked),
    )


def parse_food_feedback_callback(data: str) -> FoodFeedbackCallback | None:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "food":
        return None
    try:
        rank = int(parts[2])
        action = FoodFeedbackAction(parts[3])
    except (ValueError, TypeError):
        return None
    if not parts[1] or rank < 1:
        return None
    return FoodFeedbackCallback(parts[1], rank, action)


def apply_food_feedback_callback(
    store: PersonalContextRepositoryPort,
    data: str,
    *,
    callback_query_id: str,
) -> str | None:
    callback = parse_food_feedback_callback(data)
    if callback is None:
        return None
    candidates = store.list_recommendation_candidates(session_id=callback.session_id)
    candidate = next((row for row in candidates if int(row["rank"]) == callback.rank), None)
    if candidate is None or not candidate["place_id"]:
        return None
    record_food_feedback(
        store,
        FoodFeedback(
            feedback_key=f"telegram:{callback_query_id}",
            action=callback.action,
            place_id=str(candidate["place_id"]),
            recommendation_session_id=callback.session_id,
        ),
    )
    labels = {item["choice"]: item["label"] for item in FOOD_FEEDBACK_CHOICES}
    return f"Saved: {labels[callback.action.value]}"


def _feedback_keyboard(session_id: str, first_rank: int, count: int) -> dict[str, Any]:
    rows = []
    labels = {
        "liked": "좋아요",
        "disliked": "별로",
        "visited": "방문",
        "hide": "숨김",
        "more_like_this": "비슷한 곳",
    }
    for rank in range(first_rank, first_rank + min(count, 3)):
        rows.append(
            [
                {
                    "text": f"{rank} {labels[choice['choice']]}",
                    "callback_data": f"food:{session_id}:{rank}:{choice['choice']}",
                }
                for choice in FOOD_FEEDBACK_CHOICES[:3]
            ]
        )
        rows.append(
            [
                {
                    "text": f"{rank} {labels[choice['choice']]}",
                    "callback_data": f"food:{session_id}:{rank}:{choice['choice']}",
                }
                for choice in FOOD_FEEDBACK_CHOICES[3:]
            ]
        )
    return {"inline_keyboard": rows}


def _tier_label(tier: str) -> str:
    return {
        "verified": "복수 근거 확인",
        "partial": "일부 근거 확인",
        "candidate": "장소 후보",
        "needs_refresh": "재확인 필요",
    }.get(tier, tier)
