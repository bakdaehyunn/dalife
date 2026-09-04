# Honsanam Reminder migration baseline

Source repository: `/Users/hennei/workspace/honsanam-reminder-bot`

Target domain: `darchivebot.domains.life`

## Current status

The Honsanam Reminder source repo was clean at baseline.

Baseline verification observed before starting this migration plan:

- `.venv/bin/pytest` could not run because the generated console script has a stale
  shebang pointing at the old `life-reminder-bot` virtualenv path.
- `.venv/bin/python -m pytest`: 88 passed.

This is an environment issue in the source repo, not a behavior failure in the tests.

## Public behavior to preserve

Public CLI entry point:

- `honsanam-reminder`

Commands to preserve where practical:

- `honsanam-reminder init`
- `honsanam-reminder setup`
- `honsanam-reminder doctor`
- `honsanam-reminder discover-chat`
- `honsanam-reminder preview --date <date> --time <time>`
- `honsanam-reminder next --days <n>`
- `honsanam-reminder run-once --dry-run`
- `honsanam-reminder run-once`
- `honsanam-reminder poll-replies`
- `honsanam-reminder poll-replies --watch`
- `honsanam-reminder pending`
- `honsanam-reminder interactions`
- `honsanam-reminder interactions --json`
- `honsanam-reminder answer <confirmation-id> yes`
- `honsanam-reminder answer <confirmation-id> no`
- `honsanam-reminder send-test`
- `honsanam-reminder list`
- `honsanam-reminder show <reminder-id>`
- `honsanam-reminder disable <reminder-id>`
- `honsanam-reminder enable <reminder-id>`
- `honsanam-reminder add custom ...`
- `honsanam-reminder update <reminder-id> ...`
- `honsanam-reminder remove <reminder-id>`
- `honsanam-reminder pattern show`
- `honsanam-reminder pattern set ...`
- `honsanam-reminder validate`

## Configuration and private state

Configuration keys currently used by Honsanam Reminder include:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_REMINDER_CHAT_ID`
- `LIFE_REMINDER_TIMEZONE`

Known local state:

- `.local/state/sent.json`
- `.local/state/confirmations.json`
- `.local/state/interactions.json`
- `.local/state/run.lock`
- `.local/config/*.json`

Default routines include haircut booking, fingernails, toenails, nose hair, eyebrows,
earwax, toothbrush replacement, recycling/trash, Mac status, weekend cleaning,
bathroom cleaning, and bedding wash.

## Existing architecture

Current scheduled flow:

```text
launchd sender every 5 minutes
  -> honsanam-reminder run-once
  -> reminder schedule/rules
  -> sent.json dedupe
  -> Telegram message
  -> optional confirmation or interaction state

launchd reply watcher
  -> honsanam-reminder poll-replies --watch
  -> Telegram callback polling
  -> confirmations.json or interactions.json
  -> optional Telegram message markup edit
```

## Migration risks

- Pending Telegram callback payloads must remain understandable after migration.
- JSON state import must be idempotent.
- Existing reminder IDs are user-facing and should remain stable.
- Launchd sender and reply watcher must not double-send after Darchive scheduling is
  introduced.

## Target mapping

Move into `darchivebot.domains.life` in stages:

- reminder definitions and schedule rules,
- confirmation and interaction models,
- Telegram callback parsing and rendering,
- JSON-state importer,
- SQLite-backed repositories,
- scheduler commands and compatibility CLI wrappers.

The life domain should expose pure schedule and state-transition functions first.
Telegram transport, launchd installation, and CLI printing should remain adapter
code outside the domain.

## SQLite import

The canonical repo now provides an idempotent importer:

```text
darchive life import-honsanam --root /path/to/honsanam-reminder-bot --dry-run
darchive life import-honsanam --root /path/to/honsanam-reminder-bot
darchive life run-once --dry-run --json
```

It imports the effective fixed and custom reminder definitions, `sent.json`,
`interactions.json`, and `confirmations.json`. Sent and interaction records with the
same legacy reminder ID and scheduled timestamp become one reminder occurrence.
Confirmation payloads retain their legacy IDs, prompt state, last response, follow-up
interval, and Telegram update offset. Re-running the import updates the same rows.

The native sender reads fixed overrides and custom one-off, weekly, and interval
schedules from SQLite. It atomically claims each due event before sending, records
the Telegram message ID, retries persisted failures, and schedules a configured
follow-up after an `아직` response. The unified Telegram poller accepts both native
`life:` callbacks and already-issued Honsanam `confirm:`/`interact:` callbacks.
The `life-send` scheduler declaration is not launchd-managed yet, so installing the
current Darchive launch agents cannot create duplicate life reminders.

The local source state has been imported and refreshed idempotently in Darchive
SQLite: 12 reminders, 138 sent keys, 95 interaction records, and 4 confirmation
records. The legacy JSON files were not modified. The importer now supersedes older
pending occurrences in the same confirmation stream: three historical haircut
records are retained as `superseded`, while the latest September occurrence remains
pending. The cutover audit therefore reports no overdue confirmations.

## Compatibility wrapper

Darchivebot exposes a temporary `honsanam-reminder` console script during migration.
The following commands now route directly to the SQLite-backed Darchive life domain:

- `preview`, `next`, `run-once`, `pattern show/set`
- `list`, `show`, `enable`, `disable`, `add custom`, `update`, `remove`, `validate`
- `pending`, `interactions`, `answer`
- `init`, `doctor`, `discover-chat`, `send-test`

Setup invocations that only configure credentials, chat ID, and timezone now route
to Darchive. Setup with `--install-launchd` and reply polling commands still
delegate to the existing Honsanam source CLI:

- `/Users/hennei/workspace/honsanam-reminder-bot/.venv/bin/honsanam-reminder`
- fallback: `/Users/hennei/workspace/honsanam-reminder-bot/.venv/bin/python -m life_reminder.cli`

Set `DARCHIVE_HONSANAM_REMINDER_CLI` to override the delegated command path. The
override also forces migrated commands through the legacy CLI for rollback. The
Python-module fallback exists because the source repo currently has a stale pytest
console-script shebang, and the same kind of virtualenv path drift should not block
CLI compatibility during migration.

## Remaining compatibility work

- CLI command parser compatibility for existing `honsanam-reminder` commands.
- Consolidate the remaining setup contract before removing the compatibility
  wrapper. Reply polling is already handled by the unified
  Darchive Telegram process but remains delegated as a standalone legacy command.
- Perform a controlled live send and callback smoke test in the registered room.
- Disable the legacy Honsanam launchd sender/reply jobs before enabling Darchive's
  `life-send` launchd entry.

Run `darchive schedule cutover-check --json` before a controlled cutover. The
audit is read-only and requires all of the following before it reports ready:

- both legacy Honsanam sender and reply agents are stopped,
- native personal Telegram routing is explicitly enabled,
- the Darchive Telegram agent is loaded,
- the native life sender plist has been generated with the explicit
  `--include-life-sender` cutover flag,
- no imported confirmation follow-ups are overdue.

The command intentionally does not modify launchd or resolve old confirmations.
Those actions remain an explicit operator decision because either can change live
Telegram behavior.

Controlled cutover sequence (do not overlap senders):

1. Run `darchive life run-once --dry-run` and review pending confirmations.
2. Generate, but do not load, the native sender definition with
   `python -m darchivebot.launchd write <repo> --include-life-sender`.
3. Stop the legacy sender and reply watcher.
4. Set `DARCHIVE_NATIVE_PERSONAL_TELEGRAM=true` and restart the existing Darchive
   Telegram agent.
5. Run `darchive schedule cutover-check`; proceed only when it reports `READY`.
6. Load `com.hennei.darchivebot.life-send.plist`, then observe one scheduled cycle.

Rollback is the reverse: unload the native life sender, restore the native-personal
gate to `false`, restart Darchive Telegram, and reload the two unchanged legacy
agents. SQLite imports are retained because they are idempotent migration state,
not a reason to delete legacy JSON.
