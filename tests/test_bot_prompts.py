from __future__ import annotations

from darchivebot.bot_prompts import (
    create_post_process_prompt,
    create_project_seed_digest_prompt,
    create_revisit_digest_prompt,
)
from darchivebot.storage import ArchiveStore


def test_post_process_prompt_created_for_low_confidence_archive_item(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = add_prompt_archive_item(
        store,
        message_id=1,
        confidence=0.2,
        needs_review=True,
        primary_interest="other/unknown",
        topic="",
    )

    prompt = create_post_process_prompt(store, capture_id)

    assert prompt is not None
    assert prompt["prompt_type"] == "review_classification"
    assert prompt["chat_id"] == "chat"
    assert "Needs review" in [choice["label"] for choice in prompt["choices"]]
    assert "Raw full text" not in prompt["body"]


def test_post_process_prompt_created_for_project_seed(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    capture_id = add_prompt_archive_item(
        store,
        message_id=2,
        confidence=0.9,
        needs_review=False,
        primary_interest="product",
        topic="archive",
        insight_seed="turn this into a phone-first product flow",
    )

    prompt = create_post_process_prompt(store, capture_id)

    assert prompt is not None
    assert prompt["prompt_type"] == "project_seed_candidate"
    assert "phone-first product flow" in prompt["body"]


def test_digest_prompts_use_revisit_and_project_seed_candidates(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    add_prompt_archive_item(
        store,
        message_id=3,
        confidence=0.9,
        needs_review=False,
        primary_interest="product",
        topic="archive",
        revisit_priority="high",
        revisit_reason="good candidate for next build",
        insight_seed="phone-first prompt flow",
    )

    revisit = create_revisit_digest_prompt(store, "chat")
    project_seed = create_project_seed_digest_prompt(store, "chat")

    assert revisit is not None
    assert revisit["prompt_type"] == "digest_revisit"
    assert "good candidate" in revisit["body"]
    assert project_seed is not None
    assert project_seed["prompt_type"] == "digest_project_seed"
    assert "phone-first prompt flow" in project_seed["body"]


def test_bot_prompt_choice_is_idempotent_and_audited(tmp_path):
    store = ArchiveStore(tmp_path / "state")
    prompt = store.create_bot_prompt(
        prompt_key="test:prompt",
        chat_id="chat",
        prompt_type="review_classification",
        title="Prompt",
        body="Body",
        recommended_action="Choose",
        choices=[{"choice": "keep", "label": "Keep"}],
    )

    first = store.record_bot_prompt_choice(prompt["id"], choice="keep", actor_user_id="42")
    second = store.record_bot_prompt_choice(prompt["id"], choice="keep", actor_user_id="42")

    assert first is not None
    assert second is not None
    assert second["selected_choice"] == "keep"
    with store.connect() as conn:
        events = list(conn.execute("SELECT * FROM bot_prompt_events WHERE prompt_id = ?", (prompt["id"],)))
    assert [event["event_type"] for event in events] == ["choice"]


def add_prompt_archive_item(
    store: ArchiveStore,
    *,
    message_id: int,
    confidence: float,
    needs_review: bool,
    primary_interest: str,
    topic: str,
    revisit_priority: str = "medium",
    revisit_reason: str = "",
    insight_seed: str = "",
) -> str:
    capture_id = store.add_capture(
        capture_key=f"chat:{message_id}",
        chat_id="chat",
        message_id=message_id,
        chat_type="private",
        chat_title="me",
        sender_user_id="42",
        sender_name="User",
        message_date=None,
        text="source text should not be fully sent",
        caption="",
        content_kind="text",
        raw_message={"message_id": message_id},
    )
    store.upsert_archive_item(
        capture_id,
        {
            "title": "Prompt archive",
            "core_summary": "Concise summary for Telegram.",
            "raw_extracted_text": "Raw full text that should remain local.",
            "source_language": "en",
            "primary_interest": primary_interest,
            "topic": topic,
            "revisit_priority": revisit_priority,
            "revisit_reason": revisit_reason,
            "insight_seed": insight_seed,
            "confidence": confidence,
            "needs_review": needs_review,
        },
    )
    store.mark_capture_processed(capture_id)
    return capture_id
