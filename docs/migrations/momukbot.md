# Momukbot migration baseline

Source repository: `/Users/hennei/workspace/momukbot`

Target domain: `darchivebot.domains.food`

## Current status

The Momukbot source repo has uncommitted recommendation-quality work. Preserve that
state and do not overwrite or revert it during the Darchivebot migration.

Baseline verification observed before starting this migration plan:

- `.venv/bin/pytest`: 207 passed.

## Public behavior to preserve

Public CLI entry point:

- `momuk`

Commands to preserve where practical:

- `momuk init`
- `momuk setup`
- `momuk doctor`
- `momuk recommend --area <area> --topic <topic> [--dry-run]`
- `momuk recommend "<natural-language request>" [--dry-run]`
- `momuk parse "<natural-language request>"`
- `momuk rooms`
- `momuk discover-chat`
- `momuk send-test --chat-id <telegram-chat-id>`
- `momuk send-test --registered`
- `momuk send-test --allowed`
- `momuk setup-telegram`
- `momuk telegram-commands show`
- `momuk telegram-commands sync`
- `momuk quota`
- `momuk events --limit <n>`
- `momuk history clear --yes`
- `momuk telegram`

Telegram commands to preserve during migration:

- `/chatid`
- `/set_chat_room`
- `/set_chat_room confirm`

## Configuration and private state

Configuration keys currently used by Momukbot include:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS`
- `TELEGRAM_ADMIN_USER_IDS`
- `MOMUK_ALLOW_ALL_CHATS`
- `MOMUK_LLM_REQUEST_PARSER_ENABLED`
- `MOMUK_STORE_RAW_RESPONSE`
- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `NAVER_DAILY_SOFT_LIMIT`
- `KAKAO_REST_API_KEY`
- `BLOG_ALLOWED_DOMAINS`
- `AGENT_PROVIDER`
- `CODEX_BIN`
- `CODEX_WORKDIR`
- `CODEX_SANDBOX`
- `CODEX_TIMEOUT_SEC`
- `MOMUK_DEFAULT_COUNT`
- `MOMUK_STATE_DIR`
- `MOMUK_LOG_DIR`

Known local state:

- `.local/state/telegram_rooms.json`
- local SQLite recommendation history and events
- launchd logs under `.local/logs/`

## Existing architecture

Current request-time flow:

```text
Telegram
  -> chat.TelegramBot
  -> core.RecommendationService
  -> search.HybridSearchProvider
     -> search.KakaoLocalCandidateProvider
     -> search.NaverBlogEvidenceProvider
  -> agent.CodexCliAgent
  -> core.formatter
  -> Telegram
```

The flow confirms places with Kakao Local, matches Naver Blog evidence, then asks
the agent to evaluate only the verified candidate set. This protects against
hallucinated places, but it can be too strict when the evidence gate removes most
local candidates.

## Migration risks

- A strict "Kakao plus Naver blog" final gate can collapse a request to too few
  recommendations.
- API queries can repeat the same neighborhoods and return the same candidates if
  collection is only request-time.
- Provider-specific matching, policy terms, and ranking rules are easy to couple
  unless they move behind domain policies and ports.
- Existing Telegram room registration behavior must keep working until the Darchive
  Telegram adapter is verified.

## Target mapping

Move into `darchivebot.domains.food` in stages:

- request parsing and recommendation intent policy,
- Kakao and Naver provider adapters,
- evidence scoring and reconciliation,
- candidate ranking and formatter logic,
- quota-aware batch collection planning,
- personal feedback and place preference scoring.

Keep provider HTTP details out of the core ranking model. Store provider responses,
query ledger rows, and reconciliation decisions in SQLite repositories under the
shared Darchive persistence boundary.

## Compatibility wrapper

Darchivebot exposes a temporary `momuk` console script during migration. `parse` and
`recommend` now route directly to the native SQLite-backed Darchive food domain.
Natural-language and `--area`/`--topic` forms are supported, and `--dry-run` does not
persist a recommendation session.

Initialization, configuration-only setup, online diagnostics, room status, chat
discovery, test sending, Telegram command menu management, and unified quota status
now route to Darchive. Setup with `--install-launchd`, the standalone Telegram
daemon, event/quality-eval views, and destructive legacy history clearing continue
to delegate to the existing Momukbot source CLI:

- `/Users/hennei/workspace/momukbot/.venv/bin/momuk`
- fallback: `/Users/hennei/workspace/momukbot/.venv/bin/python -m momukbot.cli`

Set `DARCHIVE_MOMUK_CLI` to force all commands through the legacy CLI for rollback.

## Native collection status

Darchive now owns standard-library Kakao Local and Naver Blog adapters behind food
collection ports. `darchive food run-collection` balances due queries across provider,
area, and facet, enforces provider daily soft limits from the SQLite ledger, stores all
returned places and allowed blog evidence, and backs off failed queries independently.
Evidence is reconciled to places regardless of which provider result arrives first.

Provider credentials can be moved without printing values or overwriting already-set
target keys:

```text
darchive food import-provider-config --source-env /path/to/momukbot/.env --dry-run
darchive food import-provider-config --source-env /path/to/momukbot/.env
```

The unified scheduler declares a daily 03:00 collection run capped at 20 queries and
20 quota units. Existing Momukbot runtime and repository state remain untouched.

The legacy recommendation database has been imported into shared SQLite as 66
request sessions and 1,277 candidates; 101 candidates were linked to an existing
place by an unambiguous normalized-name match. Re-running the importer skips all
previously recorded source row IDs. Historical raw model responses are not copied.

Selected home-area and Itaewon history can seed exact-place refresh queries through
`darchive food plan-history-refresh`. These remain collection targets until current
Kakao and Naver evidence validates them; legacy frequency alone never promotes a
place to verified status.

Provider quota usage is recorded per immutable `query_ledger_runs` row. Existing
pre-migration `last_run_at` values are counted as a compatibility baseline, avoiding
the previous undercount when one ledger query executes more than once.

A bounded 20-query verification batch completed without provider failures, split
equally between Kakao and Naver. It increased local coverage from 121 to 199 places
and from 634 to 1,062 evidence items. Subsequent SQLite-only checks returned 30
ranked results for both the home area and Itaewon while retaining verified, partial,
and discovery-candidate evidence tiers.

## Remaining compatibility work

- Decide whether legacy event-log commands need import or can remain archived with
  the old repository. Recommendation SQLite history is imported idempotently with
  `darchive food import-momuk-history`.
- Keep launchd-installing setup delegated until the controlled Telegram cutover;
  provider and Telegram configuration-only options are already canonical.
- Run a controlled native Telegram recommendation and feedback smoke test before
  enabling the personal Telegram migration flag.
