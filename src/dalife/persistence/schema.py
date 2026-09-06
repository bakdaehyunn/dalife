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

CREATE TABLE IF NOT EXISTS areas (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE,
  parent_area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  center_latitude REAL,
  center_longitude REAL,
  radius_meters INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS places (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  provider_place_id TEXT NOT NULL,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  category TEXT,
  address TEXT,
  road_address TEXT,
  phone TEXT,
  map_url TEXT,
  area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  latitude REAL,
  longitude REAL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(provider, provider_place_id)
);

CREATE TABLE IF NOT EXISTS evidence_items (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  external_id TEXT,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  snippet TEXT NOT NULL,
  author TEXT,
  published_at TEXT,
  collected_at TEXT NOT NULL,
  query_text TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(provider, url)
);

CREATE TABLE IF NOT EXISTS place_evidence (
  id TEXT PRIMARY KEY,
  place_id TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  evidence_item_id TEXT NOT NULL REFERENCES evidence_items(id) ON DELETE CASCADE,
  match_type TEXT NOT NULL,
  score REAL NOT NULL,
  matched_terms_json TEXT NOT NULL DEFAULT '[]',
  decision TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(place_id, evidence_item_id)
);

CREATE TABLE IF NOT EXISTS tags (
  id TEXT PRIMARY KEY,
  tag_type TEXT NOT NULL,
  name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tag_type, normalized_name)
);

CREATE TABLE IF NOT EXISTS place_tags (
  place_id TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  PRIMARY KEY(place_id, tag_id, source)
);

CREATE TABLE IF NOT EXISTS query_ledger (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  provider TEXT NOT NULL,
  query_text TEXT NOT NULL,
  area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  facet TEXT NOT NULL DEFAULT '',
  sort_mode TEXT NOT NULL DEFAULT '',
  page INTEGER NOT NULL DEFAULT 1,
  quota_cost INTEGER NOT NULL DEFAULT 1,
  yielded_count INTEGER NOT NULL DEFAULT 0,
  failure_reason TEXT NOT NULL DEFAULT '',
  last_run_at TEXT,
  next_run_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(domain, provider, query_text, facet, sort_mode, page)
);

CREATE TABLE IF NOT EXISTS query_ledger_runs (
  id TEXT PRIMARY KEY,
  ledger_id TEXT NOT NULL REFERENCES query_ledger(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  quota_cost INTEGER NOT NULL,
  status TEXT NOT NULL,
  yielded_count INTEGER NOT NULL DEFAULT 0,
  failure_reason TEXT NOT NULL DEFAULT '',
  run_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routines (
  id TEXT PRIMARY KEY,
  routine_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  routine_id TEXT REFERENCES routines(id) ON DELETE SET NULL,
  reminder_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  cadence TEXT NOT NULL,
  schedule_json TEXT NOT NULL DEFAULT '{}',
  action TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  requires_confirmation INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
  setting_key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminder_events (
  id TEXT PRIMARY KEY,
  reminder_id TEXT NOT NULL REFERENCES reminders(id) ON DELETE CASCADE,
  event_key TEXT NOT NULL UNIQUE,
  due_at TEXT NOT NULL,
  status TEXT NOT NULL,
  telegram_message_id TEXT,
  response_payload_json TEXT NOT NULL DEFAULT '{}',
  sent_at TEXT,
  responded_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendation_sessions (
  id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  request_text TEXT NOT NULL,
  area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_candidates (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES recommendation_sessions(id) ON DELETE CASCADE,
  place_id TEXT REFERENCES places(id) ON DELETE SET NULL,
  rank INTEGER,
  score REAL NOT NULL DEFAULT 0.0,
  score_breakdown_json TEXT NOT NULL DEFAULT '{}',
  evidence_tier TEXT NOT NULL,
  explanation TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_feedback (
  id TEXT PRIMARY KEY,
  feedback_key TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL,
  action TEXT NOT NULL,
  place_id TEXT REFERENCES places(id) ON DELETE SET NULL,
  reminder_event_id TEXT REFERENCES reminder_events(id) ON DELETE SET NULL,
  recommendation_session_id TEXT REFERENCES recommendation_sessions(id) ON DELETE SET NULL,
  course_plan_id TEXT REFERENCES course_plans(id) ON DELETE SET NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_plans (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  area_id TEXT REFERENCES areas(id) ON DELETE SET NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  feedback_summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS course_plan_stops (
  id TEXT PRIMARY KEY,
  course_plan_id TEXT NOT NULL REFERENCES course_plans(id) ON DELETE CASCADE,
  stop_order INTEGER NOT NULL,
  source_domain TEXT NOT NULL,
  title TEXT NOT NULL,
  place_id TEXT REFERENCES places(id) ON DELETE SET NULL,
  reminder_event_id TEXT REFERENCES reminder_events(id) ON DELETE SET NULL,
  archive_item_id TEXT REFERENCES archive_items(id) ON DELETE SET NULL,
  reason TEXT NOT NULL DEFAULT '',
  starts_at TEXT,
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  UNIQUE(course_plan_id, stop_order)
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
CREATE INDEX IF NOT EXISTS idx_places_area ON places(area_id, normalized_name);
CREATE INDEX IF NOT EXISTS idx_evidence_items_collected ON evidence_items(provider, collected_at);
CREATE INDEX IF NOT EXISTS idx_place_evidence_place ON place_evidence(place_id, score);
CREATE INDEX IF NOT EXISTS idx_query_ledger_due ON query_ledger(domain, provider, next_run_at);
CREATE INDEX IF NOT EXISTS idx_query_ledger_runs_provider_time ON query_ledger_runs(provider, run_at);
CREATE INDEX IF NOT EXISTS idx_reminder_events_due ON reminder_events(status, due_at);
CREATE INDEX IF NOT EXISTS idx_recommendation_sessions_created ON recommendation_sessions(domain, created_at);
CREATE INDEX IF NOT EXISTS idx_recommendation_candidates_session ON recommendation_candidates(session_id, rank);
CREATE INDEX IF NOT EXISTS idx_user_feedback_domain_created ON user_feedback(domain, created_at);
CREATE INDEX IF NOT EXISTS idx_course_plan_stops_plan ON course_plan_stops(course_plan_id, stop_order);

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
