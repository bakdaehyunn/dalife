# DaLife

DaLife is a local, Telegram-first personal assistant for:

- collecting and searching personal archive captures;
- building evidence-backed restaurant data;
- learning food preferences from explicit behavior;
- sending life reminders and restaurant visit confirmations;
- preparing personal course drafts when enough context exists.

SQLite is the source of truth. DaLife does not require a graph database, vector
database, local web UI, or a separate machine-learning service.

## Setup

Requirements:

- macOS
- Python 3.12+
- a Telegram bot token and private chat ID
- Kakao Local and Naver Search credentials for food collection

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/dalife setup
.venv/bin/dalife doctor
```

The main environment variables are:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_ADMIN_USER_IDS=
KAKAO_REST_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
DALIFE_NATIVE_PERSONAL_TELEGRAM=true
DALIFE_LIFE_TIMEZONE=Asia/Seoul
```

## Active CLI

```bash
dalife init
dalife setup
dalife doctor [--online]
dalife discover-chat
dalife rooms
dalife telegram-commands show|sync
dalife telegram

dalife archive pending
dalife archive process
dalife archive list
dalife archive search <query>
dalife archive review
dalife archive show <capture-id>

dalife food parse "신정동 한식 추천"
dalife food plan-collection --area 신정동 --persist
dalife food due-queries
dalife food run-collection --max-queries 20 --max-quota-cost 20
dalife food quota --json
dalife food collection-report --days 30 --json
dalife food zones list|add|disable|coverage
dalife food profile show|rebuild
dalife food feedback --place-id <id> --action liked
dalife food evaluate --json
dalife food recommend-local --area "신정동 생활권" --count 10

dalife life list
dalife life show <id>
dalife life add custom ...
dalife life update <id> ...
dalife life enable|disable|remove <id>
dalife life pending
dalife life interactions
dalife life preview --date YYYY-MM-DD --time HH:MM
dalife life next --date YYYY-MM-DD --days 7
dalife life run-once [--dry-run] [--json]

dalife course plan --area 이태원 --date YYYY-MM-DD --time HH:MM
dalife schedule plan
```

`life run-once` is the unified notification sender. It sends both due life
reminders and due restaurant visit confirmations through the same Telegram
client. A dry run does not create or update delivery records.

## Food Learning

The recommendation loop is:

```text
mobility zone
  -> quota-aware collection
  -> evidence reconciliation
  -> recommendation exposure
  -> explicit Telegram behavior
  -> visit confirmation
  -> reproducible preference profile
  -> personalized reranking and evaluation
```

Telegram records `map_requested` only when the user presses the callback
button. It does not claim that a direct URL was opened. Visits are recorded
only through explicit user responses.

The personal profile falls back to neutral weights until enough real behavior
has accumulated. Historical collection runs do not have novelty metrics; new
runs populate those counters.

See [docs/personal-food-learning-plan.md](docs/personal-food-learning-plan.md)
for the current milestones and data thresholds.

## Scheduling

Install or refresh the managed LaunchAgents:

```bash
scripts/install_launch_agent.sh
```

DaLife manages four jobs:

- `com.hennei.dalife.telegram`: continuous Telegram polling;
- `com.hennei.dalife.processor`: archive processing every 15 minutes;
- `com.hennei.dalife.food-collect`: daily food collection at 03:00;
- `com.hennei.dalife.life-send`: unified notifications every 15 minutes.

The processor checks SQLite before doing work and exits without invoking Codex
when there are no pending captures.

## Verification

```bash
.venv/bin/pytest -q
.venv/bin/dalife doctor
sqlite3 .local/state/dalife.sqlite3 "PRAGMA integrity_check;"
```

Runtime files remain under `.local/` and are not committed.
