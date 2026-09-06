# Viewpoint Layer

The Viewpoint Layer is the long-term product layer for DaLife.

DaLife should not stop at storing captures. The final goal is to make saved captures usable as personal viewpoint material: what the user keeps noticing, what questions keep returning, what topics are becoming important, and what older captures should come back into a new discussion.

The Viewpoint Layer sits above the archive and semantic graph. It does not replace them. It uses their validated data to help Codex discuss the user's own saved material from the user's point of view.

## Layer stack

```text
Capture Layer
  -> Telegram messages, screenshots, photos, documents, and local media files

Archive Layer
  -> SQLite source of truth for captures, files, extracted text, archive items, and processing state

Semantic Graph Layer
  -> interests, topics, concepts, claims, questions, and relation candidates generated from validated archive rows

Telegram Recommendation Layer
  -> concise prompts, inline choices, and local audit history when the user needs to classify, revisit, keep, ignore, or turn an item into a project seed

Viewpoint Layer
  -> related captures, recurring themes, unresolved questions, project seeds, periodic insight notes, and Codex discussion context
```

## User problem

The user is not only saving things to find them later. The user is trying to turn scattered interest into reusable thinking material.

The Viewpoint Layer should answer:

- What do I keep saving?
- Which saved captures belong together?
- What questions or concerns are becoming repeated?
- What project idea, decision, habit, or writing direction is forming?
- What should Codex know about my current interests before discussing a topic with me?

The layer must preserve each capture as evidence. It should not collapse the archive into one generic summary.

## What it needs from lower layers

From the Capture Layer:
- original Telegram source metadata
- local media paths
- message/caption context

From the Archive Layer:
- title
- core summary
- key points
- interests and topics
- why saved
- revisit priority and reason
- insight seed
- confidence and review state

From the Semantic Graph Layer:
- interest nodes
- topic nodes
- concept nodes
- claim nodes
- question nodes
- relation candidates

From the Telegram Recommendation Layer:
- prompt status
- selected choice
- prompt and choice audit events
- project-seed, revisit, keep, needs-review, and ignore decisions

Raw extracted text should stay out of normal Viewpoint Layer inputs by default. It can be included only through explicit local review commands when the user needs deeper analysis.

## Staged roadmap

### Stage 1: graph and archive readiness

Goal: make the existing archive inspectable before generating insights.

First commands should answer:
- Which interests exist?
- Which concepts appear often?
- Which captures are weakly classified?
- Which items were processed by fallback logic?
- Which captures are missing topics, insight seeds, or useful graph facts?

This stage should be local, read-only, and safe. It should not rewrite existing archive items.

### Stage 2: related capture discovery

Goal: show which saved items connect to each other.

Start with conservative local matching from interests, topics, concepts, and relation candidates. Codex-based relation generation can come later after the local signals are trustworthy.

Useful output:
- source capture
- related capture
- relation reason
- shared interest/topic/concept
- confidence
- needs review flag

### Stage 3: recurring themes

Goal: identify patterns that appear across multiple captures.

Themes should be evidence-backed. Every theme should point back to the archive items that support it.

Examples:
- a repeated interest in agent workflows
- a recurring concern about career direction
- a project idea forming from several saved screenshots
- a writing topic appearing across multiple captures

### Stage 4: periodic insight notes

Goal: turn a time window into a readable note.

Weekly or monthly notes should summarize:
- repeated themes
- notable captures
- unresolved questions
- useful items to revisit
- possible project or writing seeds

Insight notes should start as drafts. Telegram should ask for a short confirmation before creating or revisiting them; it should not push long raw summaries or mutate archive facts without a local controlled action.

### Stage 4.5: phone-first recommendation prompts

Goal: let the user make lightweight archive decisions from a phone without memorizing commands.

Prompts should be sent only when there is a useful choice:
- weak classification or low confidence -> classify/review
- revisit reason or high priority -> revisit/keep/ignore
- insight seed -> project seed/revisit/keep/ignore
- weekly pattern -> create local insight/later/ignore

Every prompt and button choice should be stored in SQLite as local audit history. The button choice is a user decision record first; any later archive rewrite, insight creation, or external writeback should be a separate controlled action.

### Stage 5: Codex discussion context

Goal: let Codex use the user's archive as discussion context.

When the user asks Codex about a topic, DaLife should be able to provide bounded context:
- relevant captures
- related themes
- prior questions
- recurring interests
- evidence items

This is the actual Viewpoint Layer payoff: Codex can discuss new questions with awareness of what the user has been saving and thinking about.

## First implementation phase

The next practical implementation phase should be graph and archive readiness.

Recommended scope:
- add `dalife interests`
- add `dalife concepts`
- add `dalife graph quality`
- add a read-only first version of `dalife related <capture-id>`
- add `dalife reprocess-plan` for weak/fallback archive items
- allow explicit selected reprocessing with interpretation history
- keep all commands local and inspect-first
- keep Telegram prompts concise and choice-based
- do not send full raw capture text through Telegram

This phase gives the user a way to see whether the archive is strong enough for synthesis.

Current command shape:

```bash
dalife interests
dalife interests --json
dalife concepts
dalife concepts --json
dalife graph quality
dalife graph quality --json
dalife reprocess-plan
dalife reprocess-plan --json
dalife reprocess --capture-id <capture-id> --dry-run
dalife reprocess --capture-id <capture-id>
dalife related <capture-id>
dalife related <capture-id> --json
```

The inspection commands are local and do not call Codex, create insight notes, send Telegram messages, or rewrite existing archive rows. The exception is explicit selected reprocessing: `dalife reprocess --capture-id <capture-id>` calls the processor for one chosen capture, updates the current archive row on success, and preserves previous outputs in archive interpretation history.

`dalife reprocess-plan` is the quality-repair bridge before synthesis. It lists captures whose archive rows are too weak for reliable Viewpoint Layer work, including fallback-processed rows, missing/unknown interests, missing topics, missing key points, missing insight seeds, missing questions, missing relation candidates, low confidence, and `needs_review` rows. `dalife reprocess --dry-run` previews selected candidates only. Actual archive rewrites require one explicit capture id and remain auditable through interpretation history.

## Deferred work

Do not start with:
- Codex-generated relation edges
- calendar, journal, or task automation
- public web UI
- destructive migrations

Those should wait until the archive has enough reliable capture data and the graph/readiness commands show useful signals.

## Safety rules

- SQLite remains the operational source of truth.
- The semantic graph remains a generated meaning layer.
- Codex returns structured JSON only; Python owns validation and writes.
- Raw text is excluded from normal graph and viewpoint outputs unless explicitly requested.
- Selected reprocessing must preserve prior interpretations instead of silently erasing them.
- Every generated relation, theme, or note must preserve evidence item ids.
- Generated insights start as drafts, not facts.
- Telegram prompts carry concise summaries and choices only; raw capture text and files remain local by default.
- Prompt button choices are audited as decisions, not silently applied as archive rewrites.
