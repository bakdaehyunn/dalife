from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from darchivebot.archive_values import archive_item_to_dict, record_to_dict as row_to_dict
from darchivebot.cli_formatting import (
    format_classification_preview,
    format_file_status,
    format_process_and_graph_results,
    format_search_label,
    print_process_progress,
)
from darchivebot.config import Settings
from darchivebot.graph import default_graph_path, export_graph as export_jsonld_graph
from darchivebot.insights import generate_insight_note, list_insight_notes, show_insight_note
from darchivebot.processor import CaptureProcessor
from darchivebot.readiness import concept_summary, interest_summary, related_captures, reprocess_plan
from darchivebot.search import rebuild_search_index, review_queue, search_archive
from darchivebot.semantic_graph import default_semantic_store_path, sync_semantic_store
from darchivebot.storage import ArchiveStore
from darchivebot.web import serve_local_web


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

def web_cmd(store: ArchiveStore, *, host: str, port: int) -> int:
    try:
        serve_local_web(store, host=host, port=port)
    except KeyboardInterrupt:
        print("\ndarchive local web UI stopped")
        return 0
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 2
    return 0

def reprocess_plan_cmd(
    store: ArchiveStore,
    *,
    limit: int,
    issue: str,
    fallback_only: bool,
    needs_review_only: bool,
    capture_id: str,
    json_output: bool,
) -> int:
    result = reprocess_plan(
        store,
        limit=limit,
        issue=issue,
        fallback_only=fallback_only,
        needs_review_only=needs_review_only,
        capture_id=capture_id,
    )
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"candidate_count={result['candidate_count']} showing={len(result['candidates'])}")
    if not result["candidates"]:
        print("no reprocess candidates")
        return 0
    for item in result["candidates"]:
        reasons = ",".join(reason["name"] for reason in item["candidate_reasons"])
        history = ",".join(f"{run['processor']}:{run['status']}" for run in item["processor_history"]) or "none"
        history_count = item.get("processor_history_count", len(item["processor_history"]))
        history_suffix = f"+{history_count - len(item['processor_history'])}" if history_count > len(item["processor_history"]) else ""
        current = item["current"]
        print(
            f"{item['capture_id']}\tkind={item['content_kind']}\t"
            f"interest={current['primary_interest'] or '-'} topic={current['topic'] or '-'} "
            f"confidence={current['confidence']} needs_review={str(current['needs_review']).lower()}\t"
            f"reasons={reasons}\thistory={history}{history_suffix}\t{item['title']}"
        )
    print(result["next_step"])
    return 0

def reprocess_dry_run_cmd(
    store: ArchiveStore,
    *,
    limit: int,
    issue: str,
    fallback_only: bool,
    needs_review_only: bool,
    capture_id: str,
    json_output: bool,
) -> int:
    result = reprocess_plan(
        store,
        limit=limit,
        issue=issue,
        fallback_only=fallback_only,
        needs_review_only=needs_review_only,
        capture_id=capture_id,
    )
    payload = {
        "dry_run": True,
        "would_reprocess": result["candidates"],
        "candidate_count": result["candidate_count"],
        "message": "No SQLite rows were changed. Run `darchive reprocess --capture-id <capture-id>` to reprocess one selected capture.",
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"[dry-run] would reprocess {len(result['candidates'])} of {result['candidate_count']} candidates")
    for item in result["candidates"]:
        reasons = ",".join(reason["name"] for reason in item["candidate_reasons"])
        print(f"{item['capture_id']}\treasons={reasons}\t{item['title']}")
    print(payload["message"])
    return 0

def reprocess_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    capture_id: str,
    use_codex: bool | None,
    export_graph: bool,
    json_output: bool,
) -> int:
    if not capture_id:
        message = "reprocess requires --capture-id for actual rewrites; use --dry-run to preview candidates"
        if json_output:
            print(json.dumps({"status": "error", "message": message}, ensure_ascii=False, indent=2))
        else:
            print(message)
        return 2
    processor = CaptureProcessor(settings, store)
    result = processor.reprocess_capture(
        capture_id,
        use_codex=use_codex,
        progress=None if json_output else print_process_progress,
    )
    semantic_graph_result = None
    jsonld_graph_result = None
    if export_graph and result.get("status") == "processed":
        semantic_graph_result = sync_semantic_store(store, default_semantic_store_path(settings.root))
        jsonld_graph_result = export_jsonld_graph(store, default_graph_path(settings.root))
    print(
        format_process_and_graph_results(
            [result],
            semantic_graph_result=semantic_graph_result,
            jsonld_graph_result=jsonld_graph_result,
            json_output=json_output,
        )
    )
    return 0 if result.get("status") == "processed" else 1

def interests_cmd(store: ArchiveStore, limit: int, json_output: bool) -> int:
    result = interest_summary(store, limit=limit)
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["interests"]:
        print("no interests")
        return 0
    print(f"archive_items={result['archive_items']}")
    for item in result["interests"]:
        print(
            f"{item['interest']}\ttotal={item['total_count']} "
            f"primary={item['primary_count']} secondary={item['secondary_count']}"
        )
    return 0

def concepts_cmd(store: ArchiveStore, limit: int, json_output: bool) -> int:
    result = concept_summary(store, limit=limit)
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["concepts"]:
        print("no concepts")
        return 0
    print(f"archive_items={result['archive_items']}")
    for item in result["concepts"]:
        print(f"{item['concept']}\tcount={item['count']}")
    return 0

def related_cmd(store: ArchiveStore, capture_id: str, limit: int, json_output: bool) -> int:
    result = related_captures(store, capture_id, limit=limit)
    if result is None:
        print(f"[FAIL] archived capture not found: {capture_id}")
        return 1
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if not result["related"]:
        print(f"no related captures for {result['capture_id']}")
        return 0
    print(f"capture_id={result['capture_id']} archive_item_id={result['archive_item_id']}")
    for item in result["related"]:
        reasons = "; ".join(item["reasons"]) if item["reasons"] else "-"
        print(f"{item['capture_id']}\tscore={item['score']}\t{item['title']}\t{reasons}")
    return 0

def insights_cmd(
    store: ArchiveStore,
    *,
    action: str,
    period: str,
    dry_run: bool,
    include_needs_review: bool,
    limit: int,
    insight_id: str,
    json_output: bool,
) -> int:
    if action == "list":
        result = list_insight_notes(store, limit=limit)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if not result["notes"]:
            print("no insight notes")
            return 0
        for note in result["notes"]:
            print(
                f"{note['id']}\t{note['review_status']}\t{note['period_type']}\t"
                f"evidence={note['evidence_count']}\t{note['title']}"
            )
        return 0
    if action == "generate":
        result = generate_insight_note(
            store,
            period=period,
            dry_run=dry_run,
            include_needs_review=include_needs_review,
            limit=limit,
        )
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] in {"created", "dry-run"} else 1
        if result["status"] == "created":
            note = result["note"]
            print(
                f"created draft insight note {result['insight_id']} "
                f"evidence={len(note['notable_archive_item_ids'])}"
            )
            print(note["title"])
            print(note["summary"])
            return 0
        if result["status"] == "dry-run":
            note = result["would_create"]
            print(f"[dry-run] would create draft insight note evidence={len(note['notable_archive_item_ids'])}")
            print(note["title"])
            print(note["summary"])
            return 0
        print(f"[SKIP] {result['message']}")
        if result.get("next_step"):
            print(f"next_step: {result['next_step']}")
        return 1
    if action == "show":
        result = show_insight_note(store, insight_id)
        if result is None:
            print(f"[FAIL] insight note not found: {insight_id}")
            return 1
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print(f"id: {result['id']}")
        print(f"status: {result['review_status']}")
        print(f"period: {result['period_type']} {result['period_start']}..{result['period_end']}")
        print(f"title: {result['title']}")
        print(f"summary: {result['summary']}")
        for theme in result["recurring_themes"]:
            print(f"theme: {theme.get('type')} {theme.get('name')} evidence={theme.get('evidence_count')}")
        for item in result["evidence_items"]:
            print(f"evidence: {item['archive_item_id']} {item['title']}")
        return 0
    return 2

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
