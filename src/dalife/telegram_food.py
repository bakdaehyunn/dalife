from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from dalife.domains.food import (
    FOOD_FEEDBACK_CHOICES,
    FoodFeedback,
    FoodFeedbackAction,
    FoodRecommendationContext,
    parse_food_request,
    recommend_local_food,
    record_food_feedback,
)
from dalife.ports import PersonalContextRepositoryPort


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
    for rank, item in enumerate(ranked, start=1):
        place = item.place
        lines = [
            f"{rank}/{len(ranked)}  {place.name}",
            place.category or "분류 없음",
        ]
        if place.address:
            lines.append(place.address)
        lines.append(f"근거: {_tier_label(place.evidence_tier.value)}")
        messages.append(
            FoodTelegramMessage(
                "\n".join(lines),
                _feedback_keyboard(result.session_id, rank),
            )
        )
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
    chat_id: str = "",
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
    if callback.action == FoodFeedbackAction.VISIT_PLANNED:
        store.schedule_food_visit_followup(
            followup_key=f"visit:{callback.session_id}:{candidate['place_id']}",
            recommendation_session_id=callback.session_id,
            place_id=str(candidate["place_id"]),
            candidate_rank=callback.rank,
            chat_id=chat_id,
            due_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        )
    elif callback.action in {FoodFeedbackAction.VISIT_CONFIRMED, FoodFeedbackAction.VISIT_SKIPPED}:
        store.update_food_visit_followup(
            recommendation_session_id=callback.session_id,
            place_id=str(candidate["place_id"]),
            status="confirmed" if callback.action == FoodFeedbackAction.VISIT_CONFIRMED else "skipped",
        )
    labels = {item["choice"]: item["label"] for item in FOOD_FEEDBACK_CHOICES}
    labels.update({"visit_confirmed": "Visited", "visit_skipped": "Did not visit"})
    if callback.action == FoodFeedbackAction.MAP_REQUESTED:
        place = store.get_place(place_id=str(candidate["place_id"]))
        if place and place["map_url"]:
            return f"MAP:{place['map_url']}"
    if callback.action == FoodFeedbackAction.EVIDENCE_REQUESTED:
        evidence = _place_evidence(store, str(candidate["place_id"]))
        if evidence:
            return "EVIDENCE:" + "\n".join(evidence)
        return "EVIDENCE:확인된 외부 근거가 아직 없어요."
    return f"Saved: {labels[callback.action.value]}"


def send_due_food_visit_followups(
    store: PersonalContextRepositoryPort,
    api: Any,
    *,
    default_chat_id: str,
    now: datetime | None = None,
    limit: int = 20,
) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    due = store.list_due_food_visit_followups(due_at=current.isoformat(), limit=limit)
    sent = 0
    for row in due:
        chat_id = str(row.get("chat_id") or default_chat_id)
        if not chat_id:
            continue
        markup = {
            "inline_keyboard": [[
                {
                    "text": "갔어요",
                    "callback_data": f"food:{row['recommendation_session_id']}:{row['candidate_rank']}:visit_confirmed",
                },
                {
                    "text": "안 갔어요",
                    "callback_data": f"food:{row['recommendation_session_id']}:{row['candidate_rank']}:visit_skipped",
                },
            ]]
        }
        result = api.send_message(
            chat_id,
            f"{row['place_name']}에 실제로 방문했나요?",
            reply_markup=markup,
        )
        message_id = str((result.get("result") or {}).get("message_id") or "") if isinstance(result, dict) else ""
        store.update_food_visit_followup(
            followup_id=row["id"], status="sent", telegram_message_id=message_id
        )
        sent += 1
    return {"due": len(due), "sent": sent}


def _feedback_keyboard(session_id: str, rank: int) -> dict[str, Any]:
    labels = {
        "map_requested": "지도",
        "evidence_requested": "근거",
        "saved": "저장",
        "visit_planned": "방문 예정",
        "visit_confirmed": "갔어요",
        "visit_skipped": "안 갔어요",
        "liked": "좋아요",
        "disliked": "별로",
        "visited": "방문",
        "hide": "숨김",
        "more_like_this": "비슷한 곳",
    }
    choices = (
        FoodFeedbackAction.MAP_REQUESTED,
        FoodFeedbackAction.EVIDENCE_REQUESTED,
        FoodFeedbackAction.SAVED,
        FoodFeedbackAction.LIKED,
        FoodFeedbackAction.DISLIKED,
        FoodFeedbackAction.VISIT_PLANNED,
    )
    return {
        "inline_keyboard": [
            [
                {
                    "text": labels[choice.value],
                    "callback_data": f"food:{session_id}:{rank}:{choice.value}",
                }
                for choice in choices[start : start + 3]
            ]
            for start in range(0, len(choices), 3)
        ]
    }


def _tier_label(tier: str) -> str:
    return {
        "verified": "복수 근거 확인",
        "partial": "일부 근거 확인",
        "candidate": "장소 후보",
        "needs_refresh": "재확인 필요",
    }.get(tier, tier)


def _place_evidence(store: PersonalContextRepositoryPort, place_id: str) -> list[str]:
    links = store.list_place_evidence(place_ids=[place_id])
    evidence_ids = [str(row["evidence_item_id"]) for row in links[:3]]
    if not evidence_ids:
        return []
    items = {str(row["id"]): row for row in store.list_evidence_items(evidence_item_ids=evidence_ids)}
    lines = []
    for index, evidence_id in enumerate(evidence_ids, start=1):
        item = items.get(evidence_id)
        if not item:
            continue
        title = str(item["title"] or item["provider"] or "근거")
        url = str(item["url"] or "")
        lines.append(f"{index}. {title}" + (f"\n{url}" if url else ""))
    return lines
