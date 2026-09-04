# Personal context platform migration plan

This document defines the target shape for merging Momukbot and Honsanam Reminder
into Darchivebot. Darchivebot becomes the canonical repository and runtime while
the old repositories stay available until they are explicitly archived or deleted.

## Goal

Build one local personal-context platform that can:

- capture and search personal archive material,
- collect and rank food/place evidence around the user's real life areas,
- manage personal life reminders and confirmation state,
- suggest personal courses that combine places, time, routine tasks, and archive context.

The migration must preserve current behavior during the transition. Public CLI
commands and current Telegram behavior should keep working until replacement flows
are verified with tests.

## Canonical boundaries

The existing Darchivebot boundaries remain the spine of the merged project.

```text
CLI / Telegram / Web / Scheduler adapters
  -> domain workflows
  -> narrow ports and typed models
  -> focused persistence repositories
  -> SQLite source of truth
  -> derived search index and graph exports
```

The domain layer is split by cohesion:

- `archive`: current Darchive capture, archive, search, insight, and graph behavior.
- `food`: Momukbot-derived place search, evidence collection, ranking, personalization,
  and recommendation formatting.
- `life`: Honsanam-derived routines, reminder scheduling, confirmations, and interaction
  history.
- `course`: cross-domain plans that combine food candidates, personal tasks, location,
  time windows, and archive interests.

Infrastructure remains shared:

- `persistence`: SQLite schema, migrations, repositories, and generated indexes.
- `telegram_api` and Telegram adapters: transport, polling, callback dispatch, and
  command compatibility.
- `cli` and `cli_commands`: command registration and thin adapter logic.
- `semantic_graph` and `graph`: generated semantic outputs from validated SQLite rows.

## Storage decision

SQLite remains the operational source of truth. Graph/RDF output is derived from
validated SQLite rows and can be rebuilt.

Food data should be stored as normalized, auditable facts, not as one-off response
text:

- query batches and API quota ledger,
- external place identities,
- candidate places,
- evidence documents and evidence snippets,
- reconciliation decisions and drop reasons,
- user feedback, visits, saves, and negative signals,
- final recommendation sets.

Life data should migrate from JSON files into SQLite after compatibility tests exist:

- reminder definitions,
- generated occurrences,
- sent notifications,
- confirmation prompts,
- callback interactions,
- schedule and message-pattern configuration.

Course data is derived but should still be persisted when sent to the user:

- course plan metadata,
- ordered stops,
- evidence links back to food/life/archive rows,
- feedback on whether the plan was useful.

The food collection query ledger is part of the shared model because it controls
free-tier quota usage and prevents repeated identical lookups from dominating the
local database.

## Food recommendation redesign

The previous Momukbot request-time pipeline is useful for correctness but too narrow
for high-quality local recommendations. The canonical design should separate
collection from recommendation.

Collection:

- Run quota-aware batches in the background.
- Generate varied query plans instead of repeating one area/topic combination.
- Cover location grids, neighborhoods, cuisines, meal occasions, budget levels,
  solo/group contexts, open-now windows, and negative discovery queries.
- Record every query, provider response, quota cost, dedupe result, and evidence score.
- Prefer incremental refresh and stale-row repair over full repeated crawling.

Recommendation:

- Read from the local SQLite knowledge base first.
- Use live API search only to fill evidence gaps or answer a genuinely new context.
- Rank by personal fit, evidence diversity, recency, distance, occasion fit, novelty,
  and historical feedback.
- Avoid hard gating that collapses a good neighborhood into only a few results.
  Use evidence confidence tiers instead: verified, partially verified, candidate,
  and needs-refresh.
- Explain uncertainty honestly in the output.

## Life reminder redesign

Honsanam Reminder should become a life domain inside Darchivebot rather than a
separate process forever.

Migration order:

1. Import reminder definitions and pure scheduling logic behind domain APIs.
2. Preserve the existing `honsanam-reminder` CLI behavior through compatibility
   wrappers or aliases.
3. Keep Telegram callback payloads compatible until old pending messages age out.
4. Move JSON state into SQLite with an idempotent importer.
5. Replace separate launchd jobs with one Darchive scheduler only after sender and
   reply watcher behavior is verified.

## Course domain

The course domain should not own food search or life reminders. It composes existing
domain facts.

Examples:

- after work Itaewon dinner plus a low-friction errand,
- weekend cleaning reminder plus nearby brunch,
- date or friend course based on saved places and archive interests,
- revisit prompt for a previously saved place with weak evidence.

The course domain needs explicit evidence links so every recommendation can answer:

- why this place,
- why now,
- what source supported it,
- what personal preference it matched,
- what uncertainty remains.

## Compatibility strategy

Use Darchivebot as canonical code, but migrate behavior in small slices:

1. Add domain packages and target docs.
2. Add compatibility tests that lock current public commands and Telegram flows.
3. Copy selected source modules into Darchivebot with minimal adaptation.
4. Replace direct file state with ports and repositories.
5. Introduce SQLite tables and importers.
6. Switch CLI/Telegram adapters to the new domain services.
7. Retire old launchd jobs only after Darchive scheduled flows pass verification.

Do not use git subtree or repository archiving as the first step. Momukbot currently
has relevant uncommitted quality work, and the old repositories should remain
operational during migration.

## Verification gates

After each meaningful refactor:

- run the smallest domain tests affected by the change,
- run CLI compatibility tests for any command routing change,
- run Telegram tests for any callback or polling change,
- run import-cycle checks after package-level boundary changes,
- run the full Darchivebot test suite before committing or pushing.

The migration is complete only when:

- Darchivebot can run archive, food, life, and course flows from one repo,
- public command compatibility is documented and tested,
- old Telegram behavior has a verified replacement,
- source repos are no longer needed for daily operation,
- remaining repo-handling work is explicitly decided by the user.

## Current implementation status

Implemented in the Darchivebot integration branch:

- domain packages for archive, food, life, and course,
- shared SQLite tables for places, evidence, query ledger, reminders, feedback,
  recommendation sessions, and course plans,
- repository methods for area/place/evidence, query-ledger, life reminder, and course
  plan persistence,
- deterministic food request parsing, collection planning, and food place ranking
  primitives,
- Honsanam-compatible default reminder catalog, schedule calculation, and native
  `darchive life list/next/preview` read commands,
- deterministic course composition from due life events, ranked food places, and
  archive items,
- SQLite-backed course context loading that supplies those three inputs to both the
  CLI and feature-gated Telegram course handler, while rendering archive metadata
  only and never raw capture text,
- grouped `darchive archive`, `darchive food`, `darchive life`, and `darchive course`
  command surfaces for archive compatibility, dry-run/read-only planning, and local
  persistence smoke tests,
- temporary `momuk` and `honsanam-reminder` console-script wrappers that route
  migrated food and life operations natively while delegating only remaining
  legacy-only operations to the source repos with explicit rollback overrides,
- a pure Telegram intent router for archive capture, food recommendation, life
  reminder, course planning, and feedback callbacks. Current Telegram capture
  behavior remains the fallback until replacement handlers are verified,
- food feedback action vocabulary and SQLite persistence for liked, disliked,
  visited, hide, and more-like-this personalization signals,
- food recommendation session and ranked-candidate persistence so outputs can be
  audited and tied back to places, scores, and evidence tiers,
- feature-gated native Telegram food recommendations from SQLite, with bounded
  message chunks and persisted liked, disliked, visited, hide, and more-like-this
  callback actions; the gate defaults off to preserve the running capture flow,
- feature-gated native Telegram life schedule queries and course planning, with
  course plans loaded from persisted food, due reminder, and archive metadata
  context,
- SQLite-backed local food recommendation loading and `darchive food recommend-local`,
  which ranks stored places/evidence/feedback without provider or LLM calls,
- native Kakao Local and Naver Blog batch adapters, balanced due-query execution,
  provider daily quota accounting, failure backoff, and cross-order evidence
  reconciliation behind `darchive food run-collection`,
- immutable per-execution provider quota records and selective exact-place refresh
  planning from explicitly scoped legacy recommendation history,
- an idempotent Honsanam JSON-state importer and `darchive life import-honsanam`,
  covering reminder configuration, sent occurrences, interactions, confirmations,
  and legacy Telegram update offsets,
- SQLite-derived fixed and custom reminder scheduling, an idempotent native
  `darchive life run-once` sender, retryable delivery failures, confirmation
  follow-ups, and native plus legacy Telegram callback state transitions,
- SQLite-backed life reminder list/show/enable/disable/add/update/remove/validate,
  pending-confirmation, interaction-history, and manual-answer commands, with the
  `honsanam-reminder` compatibility executable routing those migrated commands
  natively and retaining an explicit legacy rollback override,
- confirmation-stream reconciliation that retains old imported records for audit
  while superseding stale pending occurrences before native delivery,
- shared SQLite application settings and native life message-pattern import,
  show/update, preview, delivery, and Telegram rendering,
- configurable life scheduling timezone through `DARCHIVE_LIFE_TIMEZONE`, retaining
  `Asia/Seoul` as the compatibility default,
- a unified scheduler plan, `darchive schedule plan` inspection command, and a
  launchd plist generator that installs only enabled executable jobs from that
  scheduler plan.
- a read-only `darchive schedule cutover-check` audit covering legacy agent
  overlap, native Telegram routing, life sender activation, and SQLite
  confirmation backlog before live migration.
- explicit opt-in generation of the native life sender plist through
  `--include-life-sender`; default launchd installation continues to exclude it,
- completed live cutover to the former Momuk shared Telegram room: native Darchive
  routing and life delivery are loaded, while the Momuk poller and both Honsanam
  launchd agents are stopped and disabled,
- controlled shared-room delivery, synchronized command menus, online diagnostics,
  and a blocker-free `schedule cutover-check` after activation,
- moved notices in both legacy repositories identifying Darchivebot as the canonical
  implementation and the old repositories as rollback references.

Not yet migrated:

- Momukbot legacy event-log/history commands and its standalone setup/room command
  surface; recommendation parsing and the normal `momuk recommend` compatibility
  path are native,
- Honsanam standalone setup and `poll-replies` command surfaces; initialization,
  online diagnostics, discovery, test sending, schedule management, message
  patterns, dispatch, and state queries route natively,
- removal of compatibility wrappers and legacy callback handling; they remain in
  place for rollback and public CLI compatibility,
- GitHub archive-state changes for the old repositories; the local environment does
  not currently have an authenticated GitHub CLI available.
