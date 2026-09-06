from __future__ import annotations

import json
from pathlib import Path

from dalife.config import Settings
from dalife.graph import default_graph_path, export_graph as export_jsonld_graph
from dalife.readiness import graph_quality_summary
from dalife.semantic_graph import (
    default_semantic_export_path,
    default_semantic_store_path,
    export_semantic_store,
    init_semantic_store,
    semantic_store_stats,
    sync_semantic_store,
)
from dalife.storage import ArchiveStore


def graph_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    action: str,
    output_path: Path | None,
    stats_path: Path | None,
    limit: int | None,
    quality_limit: int,
    include_raw_text: bool,
    json_output: bool,
) -> int:
    if action == "init":
        path = stats_path or default_semantic_store_path(settings.root)
        result = init_semantic_store(path)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"initialized semantic graph store at {result['path']}")
        return 0
    if action == "sync":
        path = stats_path or default_semantic_store_path(settings.root)
        result = sync_semantic_store(store, path, limit=limit, include_raw_text=include_raw_text)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            raw_note = " with raw text" if result.get("raw_text_included") else ""
            print(
                f"synced {result['synced_archive_items']} archive items "
                f"({result['quads']} quads){raw_note} to {result['path']}"
            )
        return 0
    if action == "store-export":
        path = stats_path or default_semantic_store_path(settings.root)
        out_path = output_path or default_semantic_export_path(settings.root)
        try:
            result = export_semantic_store(path, out_path)
        except FileNotFoundError as exc:
            print(f"[FAIL] {exc}")
            return 1
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"exported semantic graph store ({result['quads']} quads) to {result['export_path']}")
        return 0
    if action == "export":
        path = output_path or default_graph_path(settings.root)
        result = export_jsonld_graph(store, path, limit=limit, include_raw_text=include_raw_text)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            raw_note = " with raw text" if result.get("raw_text_included") else ""
            print(f"exported {result['archive_items']} archive items ({result['nodes']} nodes){raw_note} to {result['path']}")
        return 0
    if action == "stats":
        path = stats_path or default_semantic_store_path(settings.root)
        result = semantic_store_stats(path)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result["exists"]:
            print(
                f"semantic_graph={result['path']} archive_items={result['archive_items']} "
                f"quads={result['quads']} generated_at={result.get('generated_at', '')} "
                f"raw_text_included={str(result['raw_text_included']).lower()}"
            )
        else:
            print(f"semantic graph store not found: {result['path']}")
        return 0 if result["exists"] else 1
    if action == "quality":
        result = graph_quality_summary(store, limit=quality_limit)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                f"archive_items={result['archive_items']} "
                f"ready_for_synthesis={str(result['ready_for_synthesis']).lower()}"
            )
            for issue in result["issues"]:
                print(f"{issue['name']}\tcount={issue['count']}")
            print(f"next_step: {result['next_step']}")
        return 0
    return 2






























if __name__ == "__main__":
    raise SystemExit(main())
