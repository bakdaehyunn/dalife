from __future__ import annotations

import json
from typing import Any

from dalife.archive_values import archive_item_to_dict, record_to_dict as row_to_dict
from dalife.cli_formatting import (
    format_classification_preview,
    format_file_status,
    format_search_label,
)
from dalife.search import rebuild_search_index, review_queue, search_archive
from dalife.storage import ArchiveStore


def list_cmd(store: ArchiveStore, limit: int, interest: str, json_output: bool) -> int:
    rows = store.list_capture_summaries(limit, interest=interest)
    if json_output:
        print(json.dumps([row_to_dict(row) for row in rows], ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("no captures" if not interest else f"no captures for interest: {interest}")
        return 0
    for row in rows:
        text = str(row["text"] or row["caption"] or "").replace("\n", " ")
        file_status = format_file_status(row)
        archive_status = "archived" if int(row["has_archive_item"] or 0) else "not_archived"
        title = str(row["archive_title"] or "").replace("\n", " ").strip()
        core_summary = str(row["archive_core_summary"] or "").replace("\n", " ").strip()
        primary_interest = str(row["archive_primary_interest"] or "").replace("\n", " ").strip()
        topic = str(row["archive_topic"] or "").replace("\n", " ").strip()
        classification = format_classification_preview(primary_interest, topic)
        preview = title or core_summary or text[:80] or "(no text)"
        print(
            f"{row['id']}\t{row['status']}\t{row['content_kind']}\t"
            f"files={file_status}\tarchive={archive_status}{classification}\t{preview[:100]}"
        )
    return 0

def search_cmd(store: ArchiveStore, *, query: str, limit: int, rebuild: bool, json_output: bool) -> int:
    rebuild_result = rebuild_search_index(store) if rebuild else None
    result = search_archive(store, query, limit=limit)
    if json_output:
        payload: dict[str, Any] = dict(result)
        if rebuild_result is not None:
            payload["index"] = rebuild_result
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if rebuild_result is not None:
        print(f"search index rebuilt archive_items={rebuild_result['indexed_archive_items']}")
    if not result["results"]:
        print(f"no search results for: {query}")
        return 0
    print(f"query={query} results={result['count']}")
    for item in result["results"]:
        label = format_search_label(item)
        snippet = item.get("snippet") or item.get("summary") or ""
        print(f"{item['capture_id']}\t{label}\t{item['title']}")
        print(f"  why: {item['match_explanation']}")
        if snippet:
            print(f"  snippet: {snippet[:240]}")
    return 0

def review_cmd(
    store: ArchiveStore,
    *,
    limit: int,
    needs_review_only: bool,
    revisit_only: bool,
    json_output: bool,
) -> int:
    result = review_queue(
        store,
        limit=limit,
        needs_review_only=needs_review_only,
        revisit_only=revisit_only,
    )
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["items"]:
        print(f"no review items mode={result['mode']}")
        return 0
    print(f"mode={result['mode']} items={result['count']}")
    for item in result["items"]:
        flags = []
        if item["needs_review"]:
            flags.append("needs_review")
        if item["revisit_priority"]:
            flags.append(f"revisit={item['revisit_priority']}")
        label = " ".join(flags) or "review"
        topic = format_classification_preview(item["primary_interest"], item["topic"]).strip()
        print(f"{item['capture_id']}\t{label}\t{topic}\t{item['title']}")
        if item["revisit_reason"]:
            print(f"  revisit_reason: {item['revisit_reason']}")
        if item["insight_seed"]:
            print(f"  insight_seed: {item['insight_seed']}")
    return 0


def show_cmd(store: ArchiveStore, capture_id: str, json_output: bool) -> int:
    row = store.get_capture(capture_id)
    if row is None:
        print(f"[FAIL] capture not found: {capture_id}")
        return 1
    files = store.files_for_capture(capture_id)
    archive = store.get_archive_item(capture_id)
    data = row_to_dict(row)
    data["files"] = [row_to_dict(file_row) for file_row in files]
    data["archive_item"] = archive_item_to_dict(archive) if archive is not None else None
    if json_output:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"id: {data['id']}")
    print(f"status: {data['status']}")
    print(f"kind: {data['content_kind']}")
    if data.get("text"):
        print(f"text: {data['text']}")
    if data.get("caption"):
        print(f"caption: {data['caption']}")
    for file_row in data["files"]:
        print(f"file: {file_row.get('download_status')} {file_row.get('local_path')}")
    if data["archive_item"]:
        archive_item = data["archive_item"]
        print(f"archive_title: {archive_item.get('title')}")
        if archive_item.get("core_summary"):
            print(f"core_summary: {archive_item.get('core_summary')}")
        if archive_item.get("key_points"):
            for point in archive_item["key_points"]:
                print(f"key_point: {point}")
        if archive_item.get("context"):
            print(f"context: {archive_item.get('context')}")
        if archive_item.get("why_saved"):
            print(f"why_saved: {archive_item.get('why_saved')}")
        if archive_item.get("tags"):
            print(f"tags: {', '.join(archive_item['tags'])}")
        if archive_item.get("primary_interest"):
            print(f"primary_interest: {archive_item.get('primary_interest')}")
        if archive_item.get("secondary_interests"):
            print(f"secondary_interests: {', '.join(archive_item['secondary_interests'])}")
        if archive_item.get("topic"):
            print(f"topic: {archive_item.get('topic')}")
        if archive_item.get("subtopic"):
            print(f"subtopic: {archive_item.get('subtopic')}")
        if archive_item.get("classification_reason"):
            print(f"classification_reason: {archive_item.get('classification_reason')}")
        if archive_item.get("revisit_priority"):
            print(f"revisit_priority: {archive_item.get('revisit_priority')}")
        if archive_item.get("revisit_reason"):
            print(f"revisit_reason: {archive_item.get('revisit_reason')}")
        if archive_item.get("insight_seed"):
            print(f"insight_seed: {archive_item.get('insight_seed')}")
        print(f"needs_review: {archive_item.get('needs_review')}")
    return 0
