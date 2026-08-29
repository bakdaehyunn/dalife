from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def json_value(value: Any, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def json_array(value: Any) -> list[Any]:
    payload = json_value(value, [])
    return payload if isinstance(payload, list) else []


def json_string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in json_array(value) if str(item).strip()]


def raw_json_string_list(row: Mapping[str, Any], key: str) -> list[str]:
    return raw_payload_string_list(row.get("raw_codex_json"), key)


def raw_payload_string_list(raw: Any, key: str) -> list[str]:
    payload = json_value(raw, {})
    if not isinstance(payload, dict):
        return []
    return json_string_list(payload.get(key))


def semantic_string_list(row: Mapping[str, Any], column: str, raw_key: str) -> list[str]:
    normalized = json_string_list(row.get(column))
    return normalized or raw_json_string_list(row, raw_key)


def clean(value: Any) -> str:
    return str(value or "").strip()


def confidence(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def record_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return dict(row)


def archive_item_to_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    data = record_to_dict(row)
    data["core_summary"] = data.get("core_summary") or data.get("summary") or ""
    data["raw_extracted_text"] = data.get("raw_extracted_text") or data.get("extracted_text") or ""
    for key in (
        "primary_interest",
        "topic",
        "subtopic",
        "classification_reason",
        "revisit_priority",
        "revisit_reason",
        "insight_seed",
    ):
        data[key] = data.get(key) or ""
    for target, source in (
        ("key_points", "key_points_json"),
        ("tags", "tags_json"),
        ("secondary_interests", "secondary_interests_json"),
        ("questions", "questions_json"),
        ("relation_candidates", "relation_candidates_json"),
        ("dates_mentioned", "dates_mentioned_json"),
        ("people_mentioned", "people_mentioned_json"),
        ("action_candidates", "action_candidates_json"),
    ):
        data[target] = json_string_list(data.get(source))
    data["needs_review"] = bool(data.get("needs_review"))
    return data
