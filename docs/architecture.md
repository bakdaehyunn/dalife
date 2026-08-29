# 다카이브봇 아키텍처

다카이브봇은 Telegram을 개인 캡처함으로 쓰고, 로컬 SQLite를 영구 저장소로 쓰는 개인 아카이브 봇입니다.

## 흐름

```text
Telegram message/photo/document
  -> darchive telegram
  -> captures/capture_files SQLite rows
  -> downloaded media under .local/captures/

launchd/cron
  -> darchive process --export-graph
  -> pending capture packet, or retryable failure whose backoff has expired
  -> codex exec with JSON Schema
  -> validated archive_items/extracted_texts SQLite rows
  -> archive_interpretations audit row for each successful interpretation
  -> generated SQLite FTS5 search index from validated archive rows
  -> if any capture was processed, rebuild semantic graph from validated archive_items SQLite rows
  -> RDF store under .local/graph/semantic-store/
  -> lightweight JSON-LD export under .local/graph/darchivebot.jsonld

daily retrieval
  -> darchive search
  -> darchive review
  -> darchive web on 127.0.0.1
  -> archive detail, matched fields, related captures, insight notes

manual graph inspection
  -> darchive graph sync
  -> darchive graph stats
  -> darchive graph export
  -> darchive graph store-export

future Viewpoint Layer
  -> graph/readiness inspection
  -> related captures
  -> recurring themes
  -> periodic insight notes
  -> bounded Codex discussion context from the user's archive
```

## 경계

- `telegram`: compatibility surface and Telegram polling/capture orchestration.
- `telegram_api`: Telegram HTTP transport only.
- `telegram_messages`: Telegram message parsing and attachment classification.
- `telegram_rooms`: room registration, allow-list state, and command scopes.
- `telegram_prompts`: prompt rendering, inline buttons, and callback payloads.
- `storage`: thin compatibility facade that composes focused persistence repositories.
- `persistence/database`: SQLite path, connection, schema initialization, and migration entry point.
- `persistence/schema`: declarative SQLite schema.
- `persistence/search_index`: FTS schema repair, indexing, and migration helpers.
- `persistence/*_repository`: focused capture, archive, processing, search, prompt, and insight persistence.
- `models`: immutable typed records returned across the persistence boundary; mapping compatibility preserves existing Python callers without exposing `sqlite3.Row`.
- `ports`: narrow structural interfaces used by processing, retrieval, graph, insight, Telegram, and web features.
- `archive_values`: canonical JSON-column decoding and archive-item normalization.
- `ontology`: exporter-independent ontology versions, URNs, and stable semantic identifiers.
- `codex_harness`: non-interactive Codex invocation and JSON Schema setup.
- `processor`: pending capture selection, Codex result validation, fallback extraction, state transitions.
- `ocr`: optional local OCR fallback when Codex is disabled.
- `search`: generated SQLite FTS5 index, match explanation, review queues, and detail shaping for CLI/web retrieval.
- `semantic_graph`: pyoxigraph RDF store sync, stats, and N-Quads export from validated archive rows.
- `graph`: lightweight JSON-LD portable export from validated archive rows.
- `web`: loopback-only local archive workbench over SQLite search/review/detail data.
- `cli`: composition root and compatibility wrappers.
- `cli_parser`: command and argument registration.
- `cli_formatting`: terminal/JSON result formatting.
- `cli_commands/*`: cohesive setup, Telegram, archive/retrieval/insight, and graph command handlers.

## Dependency direction

```text
CLI / Web / Telegram adapters
  -> application features (processor, search, readiness, insights, graph exporters)
  -> narrow ports and typed models
  -> focused persistence repositories
  -> SQLite database, schema, migrations, and generated FTS index

graph + semantic_graph
  -> shared ontology identifiers and archive normalization
  -> archive reader port
```

Application and presentation modules do not import `sqlite3` or receive `sqlite3.Row`. The persistence layer converts rows into immutable typed records before returning them. `ArchiveStore` remains as a small compatibility facade for existing tests and public callers, while new feature annotations depend on narrow protocols from `ports`.

The JSON-LD and RDF exporters are sibling adapters. Both depend on `ontology` for identifiers; neither exporter owns the other's semantic rules.

Codex is intentionally not allowed to write SQLite directly. Codex reads a bounded capture packet and attached images, returns structured JSON, then Python validates and writes the database. This keeps database mutation deterministic and makes retry/failure handling explicit.

Failed scheduled processing is not retried immediately forever. Captures track `retry_count`, `next_retry_at`, and `last_error`; repeated failures eventually move to `failed_blocked` so launchd cannot create endless identical failure rows every five minutes.

`archive_items` is the current interpreted view of a capture. Every successful write also creates an `archive_interpretations` row with the source, schema/prompt version when available, confidence, review state, and raw structured output. Selected reprocessing can update the current view without erasing prior interpretations.

The ontology-native graph layer is a semantic memory, not the raw ingestion store. SQLite remains the source of truth for Telegram capture state and processing runs. The pyoxigraph store under `.local/graph/semantic-store/` is the primary semantic layer for interests, topics, concepts, claims, questions, and relation candidates. Questions and relation candidates are normalized onto archive rows and remain backward-compatible with older raw Codex JSON. JSON-LD remains a lightweight portable export, not a full semantic-store backup. Raw extracted text is omitted from graph output by default and only included with an explicit CLI flag.

## Product layers

```text
Capture Layer
  -> Telegram intake and local media storage

Archive Layer
  -> SQLite source of truth for captures, files, extracted text, archive items, archive interpretations, retry state, and processing runs

Search Layer
  -> generated SQLite FTS5 index, search explanations, review queues, and loopback-only local web UI

Semantic Graph Layer
  -> generated meaning layer for interests, topics, concepts, claims, questions, and relation candidates

Viewpoint Layer
  -> related captures, recurring themes, unresolved questions, project seeds, periodic insight notes, and Codex discussion context
```

The Viewpoint Layer is the final product direction. It should help the user discuss new questions with Codex using bounded context from their own saved archive. It should not bypass the lower layers: every viewpoint output needs evidence from archive items and graph facts.

## Local privacy

Secrets, logs, SQLite files, and captured media live under `.env` and `.local/`, which are gitignored. Telegram files are downloaded immediately so the local archive does not depend only on Telegram `file_id` values.
