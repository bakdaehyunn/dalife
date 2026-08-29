from __future__ import annotations


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS captures (
  id TEXT PRIMARY KEY,
  capture_key TEXT NOT NULL UNIQUE,
  chat_id TEXT NOT NULL,
  message_id INTEGER NOT NULL,
  chat_type TEXT,
  chat_title TEXT,
  sender_user_id TEXT,
  sender_name TEXT,
  message_date INTEGER,
  message_datetime TEXT,
  text TEXT,
  caption TEXT,
  content_kind TEXT NOT NULL,
  raw_message_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  retry_count INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capture_files (
  id TEXT PRIMARY KEY,
  capture_id TEXT NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  telegram_file_id TEXT NOT NULL,
  telegram_file_unique_id TEXT,
  file_kind TEXT NOT NULL,
  mime_type TEXT,
  file_name TEXT,
  file_size INTEGER,
  local_path TEXT,
  download_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(capture_id, telegram_file_id)
);

CREATE TABLE IF NOT EXISTS extracted_texts (
  id TEXT PRIMARY KEY,
  capture_id TEXT NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(capture_id, source)
);

CREATE TABLE IF NOT EXISTS archive_items (
  id TEXT PRIMARY KEY,
  capture_id TEXT NOT NULL UNIQUE REFERENCES captures(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  core_summary TEXT,
  key_points_json TEXT,
  context TEXT,
  extracted_text TEXT NOT NULL,
  raw_extracted_text TEXT,
  why_saved TEXT,
  source_language TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  primary_interest TEXT,
  secondary_interests_json TEXT,
  topic TEXT,
  subtopic TEXT,
  classification_reason TEXT,
  revisit_priority TEXT,
  revisit_reason TEXT,
  insight_seed TEXT,
  questions_json TEXT NOT NULL DEFAULT '[]',
  relation_candidates_json TEXT NOT NULL DEFAULT '[]',
  dates_mentioned_json TEXT NOT NULL,
  people_mentioned_json TEXT NOT NULL,
  action_candidates_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL,
  raw_codex_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_runs (
  id TEXT PRIMARY KEY,
  capture_id TEXT REFERENCES captures(id) ON DELETE SET NULL,
  processor TEXT NOT NULL,
  status TEXT NOT NULL,
  input_path TEXT,
  output_path TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS archive_interpretations (
  id TEXT PRIMARY KEY,
  capture_id TEXT NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
  archive_item_id TEXT NOT NULL REFERENCES archive_items(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  schema_version TEXT,
  prompt_version TEXT,
  title TEXT NOT NULL,
  core_summary TEXT,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL,
  raw_item_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insight_notes (
  id TEXT PRIMARY KEY,
  period_type TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  recurring_themes_json TEXT NOT NULL,
  related_capture_groups_json TEXT NOT NULL,
  notable_archive_item_ids_json TEXT NOT NULL,
  questions_json TEXT NOT NULL,
  suggested_reviews_json TEXT NOT NULL,
  review_status TEXT NOT NULL,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL,
  generator TEXT NOT NULL,
  raw_codex_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insight_note_items (
  id TEXT PRIMARY KEY,
  insight_note_id TEXT NOT NULL REFERENCES insight_notes(id) ON DELETE CASCADE,
  archive_item_id TEXT NOT NULL REFERENCES archive_items(id) ON DELETE CASCADE,
  evidence_role TEXT NOT NULL,
  evidence_order INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(insight_note_id, archive_item_id)
);

CREATE TABLE IF NOT EXISTS bot_prompts (
  id TEXT PRIMARY KEY,
  prompt_key TEXT NOT NULL UNIQUE,
  chat_id TEXT NOT NULL,
  prompt_type TEXT NOT NULL,
  status TEXT NOT NULL,
  capture_id TEXT REFERENCES captures(id) ON DELETE SET NULL,
  archive_item_id TEXT REFERENCES archive_items(id) ON DELETE SET NULL,
  insight_note_id TEXT REFERENCES insight_notes(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  choices_json TEXT NOT NULL,
  selected_choice TEXT,
  selected_payload_json TEXT NOT NULL DEFAULT '{}',
  telegram_message_id TEXT,
  created_at TEXT NOT NULL,
  sent_at TEXT,
  responded_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_prompt_events (
  id TEXT PRIMARY KEY,
  prompt_id TEXT NOT NULL REFERENCES bot_prompts(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  choice TEXT,
  actor_user_id TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_captures_status_created ON captures(status, created_at);
CREATE INDEX IF NOT EXISTS idx_capture_files_capture_id ON capture_files(capture_id);
CREATE INDEX IF NOT EXISTS idx_processing_runs_capture_id ON processing_runs(capture_id);
CREATE INDEX IF NOT EXISTS idx_archive_interpretations_capture_id ON archive_interpretations(capture_id, created_at);
CREATE INDEX IF NOT EXISTS idx_insight_notes_period ON insight_notes(period_type, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_insight_note_items_archive_item_id ON insight_note_items(archive_item_id);
CREATE INDEX IF NOT EXISTS idx_bot_prompts_status_created ON bot_prompts(status, created_at);
CREATE INDEX IF NOT EXISTS idx_bot_prompts_capture ON bot_prompts(capture_id);
CREATE INDEX IF NOT EXISTS idx_bot_prompt_events_prompt ON bot_prompt_events(prompt_id, created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS archive_search_fts USING fts5(
  archive_item_id UNINDEXED,
  capture_id UNINDEXED,
  title,
  summary,
  extracted_text,
  tags,
  interests,
  topics,
  questions,
  insight_seed,
  source_text,
  tokenize = 'unicode61'
);
"""

