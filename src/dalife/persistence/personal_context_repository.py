from __future__ import annotations

import json
import uuid
from typing import Any

from dalife.json_utils import dumps
from dalife.models import (
    AreaRecord,
    CoursePlanRecord,
    CoursePlanStopRecord,
    EvidenceItemRecord,
    PlaceEvidenceRecord,
    PlaceRecord,
    QueryLedgerRecord,
    RecommendationCandidateRecord,
    RecommendationSessionRecord,
    ReminderEventRecord,
    ReminderRecord,
    RoutineRecord,
    UserFeedbackRecord,
)
from dalife.persistence.common import optional_record, records, utc_now
from dalife.persistence.database import RepositoryBase


class PersonalContextRepository(RepositoryBase):
    def get_app_setting(self, *, setting_key: str) -> dict[str, Any] | None:
        self.init_db()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value_json FROM app_settings WHERE setting_key = ?",
                (setting_key,),
            ).fetchone()
        if row is None:
            return None
        value = json.loads(str(row["value_json"] or "{}"))
        return value if isinstance(value, dict) else None

    def set_app_setting(self, *, setting_key: str, value: dict[str, Any]) -> dict[str, Any]:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings(setting_key, value_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET
                  value_json = excluded.value_json,
                  updated_at = excluded.updated_at
                """,
                (setting_key, dumps(value), now, now),
            )
        return dict(value)

    def get_area(self, *, area_id: str) -> AreaRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(
                conn.execute("SELECT * FROM areas WHERE id = ?", (area_id,)).fetchone(),
                AreaRecord,
            )

    def get_area_by_normalized_name(self, *, normalized_name: str) -> AreaRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(
                conn.execute(
                    "SELECT * FROM areas WHERE normalized_name = ?",
                    (normalized_name,),
                ).fetchone(),
                AreaRecord,
            )

    def list_areas(self) -> list[AreaRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(conn.execute("SELECT * FROM areas ORDER BY name"), AreaRecord)

    def upsert_area(
        self,
        *,
        name: str,
        normalized_name: str,
        center_latitude: float | None = None,
        center_longitude: float | None = None,
        radius_meters: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AreaRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO areas(
                  id, name, normalized_name, center_latitude, center_longitude,
                  radius_meters, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_name) DO UPDATE SET
                  name = excluded.name,
                  center_latitude = excluded.center_latitude,
                  center_longitude = excluded.center_longitude,
                  radius_meters = excluded.radius_meters,
                  metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    name,
                    normalized_name,
                    center_latitude,
                    center_longitude,
                    radius_meters,
                    dumps(metadata or {}),
                    now,
                    now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM areas WHERE normalized_name = ?", (normalized_name,)).fetchone(),
                AreaRecord,
            )

    def upsert_place(
        self,
        *,
        provider: str,
        provider_place_id: str,
        name: str,
        normalized_name: str,
        area_id: str = "",
        category: str = "",
        address: str = "",
        road_address: str = "",
        phone: str = "",
        map_url: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PlaceRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO places(
                  id, provider, provider_place_id, name, normalized_name, category,
                  address, road_address, phone, map_url, area_id, latitude, longitude,
                  first_seen_at, last_seen_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULLIF(?, ''), ?, ?, ?, ?, ?)
                ON CONFLICT(provider, provider_place_id) DO UPDATE SET
                  name = excluded.name,
                  normalized_name = excluded.normalized_name,
                  category = excluded.category,
                  address = excluded.address,
                  road_address = excluded.road_address,
                  phone = excluded.phone,
                  map_url = excluded.map_url,
                  area_id = excluded.area_id,
                  latitude = excluded.latitude,
                  longitude = excluded.longitude,
                  last_seen_at = excluded.last_seen_at,
                  metadata_json = excluded.metadata_json
                """,
                (
                    str(uuid.uuid4()),
                    provider,
                    provider_place_id,
                    name,
                    normalized_name,
                    category,
                    address,
                    road_address,
                    phone,
                    map_url,
                    area_id,
                    latitude,
                    longitude,
                    now,
                    now,
                    dumps(metadata or {}),
                ),
            )
            return optional_record(
                conn.execute(
                    "SELECT * FROM places WHERE provider = ? AND provider_place_id = ?",
                    (provider, provider_place_id),
                ).fetchone(),
                PlaceRecord,
            )

    def list_places(self, *, area_id: str = "", limit: int = 500) -> list[PlaceRecord]:
        self.init_db()
        sql = "SELECT * FROM places WHERE 1 = 1"
        params: list[Any] = []
        if area_id:
            sql += " AND area_id = ?"
            params.append(area_id)
        sql += " ORDER BY last_seen_at DESC, name LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), PlaceRecord)

    def upsert_evidence_item(
        self,
        *,
        provider: str,
        url: str,
        title: str,
        snippet: str,
        external_id: str = "",
        author: str = "",
        published_at: str = "",
        query_text: str = "",
        raw: dict[str, Any] | None = None,
        area_id: str = "",
    ) -> EvidenceItemRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO evidence_items(
                  id, provider, area_id, external_id, url, title, snippet, author, published_at,
                  collected_at, query_text, raw_json
                )
                VALUES (?, ?, NULLIF(?, ''), ?, ?, ?, ?, ?, NULLIF(?, ''), ?, ?, ?)
                ON CONFLICT(provider, url) DO UPDATE SET
                  area_id = COALESCE(excluded.area_id, evidence_items.area_id),
                  external_id = excluded.external_id,
                  title = excluded.title,
                  snippet = excluded.snippet,
                  author = excluded.author,
                  published_at = excluded.published_at,
                  collected_at = excluded.collected_at,
                  query_text = excluded.query_text,
                  raw_json = excluded.raw_json
                """,
                (
                    str(uuid.uuid4()),
                    provider,
                    area_id,
                    external_id,
                    url,
                    title,
                    snippet,
                    author,
                    published_at,
                    now,
                    query_text,
                    dumps(raw or {}),
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM evidence_items WHERE provider = ? AND url = ?", (provider, url)).fetchone(),
                EvidenceItemRecord,
            )

    def list_evidence_items_for_area(
        self,
        *,
        area_id: str,
        provider: str = "",
        limit: int = 5000,
    ) -> list[EvidenceItemRecord]:
        self.init_db()
        sql = "SELECT * FROM evidence_items WHERE area_id = ?"
        params: list[Any] = [area_id]
        if provider:
            sql += " AND provider = ?"
            params.append(provider)
        sql += " ORDER BY collected_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), EvidenceItemRecord)

    def link_place_evidence(
        self,
        *,
        place_id: str,
        evidence_item_id: str,
        match_type: str,
        score: float,
        decision: str,
        matched_terms: list[str] | None = None,
    ) -> PlaceEvidenceRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO place_evidence(
                  id, place_id, evidence_item_id, match_type, score,
                  matched_terms_json, decision, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(place_id, evidence_item_id) DO UPDATE SET
                  match_type = excluded.match_type,
                  score = excluded.score,
                  matched_terms_json = excluded.matched_terms_json,
                  decision = excluded.decision
                """,
                (
                    str(uuid.uuid4()),
                    place_id,
                    evidence_item_id,
                    match_type,
                    score,
                    dumps(matched_terms or []),
                    decision,
                    now,
                ),
            )
            return optional_record(
                conn.execute(
                    "SELECT * FROM place_evidence WHERE place_id = ? AND evidence_item_id = ?",
                    (place_id, evidence_item_id),
                ).fetchone(),
                PlaceEvidenceRecord,
            )

    def list_place_evidence(
        self,
        *,
        place_ids: list[str],
        decisions: tuple[str, ...] = ("matched", "verified"),
    ) -> list[PlaceEvidenceRecord]:
        self.init_db()
        if not place_ids or not decisions:
            return []
        place_slots = ",".join("?" for _ in place_ids)
        decision_slots = ",".join("?" for _ in decisions)
        with self.connect() as conn:
            return records(
                conn.execute(
                    f"""
                    SELECT *
                    FROM place_evidence
                    WHERE place_id IN ({place_slots})
                      AND decision IN ({decision_slots})
                    ORDER BY score DESC, created_at DESC
                    """,
                    [*place_ids, *decisions],
                ),
                PlaceEvidenceRecord,
            )

    def list_evidence_items(self, *, evidence_item_ids: list[str]) -> list[EvidenceItemRecord]:
        self.init_db()
        if not evidence_item_ids:
            return []
        slots = ",".join("?" for _ in evidence_item_ids)
        with self.connect() as conn:
            return records(
                conn.execute(
                    f"SELECT * FROM evidence_items WHERE id IN ({slots})",
                    evidence_item_ids,
                ),
                EvidenceItemRecord,
            )

    def upsert_query_ledger_entry(
        self,
        *,
        domain: str,
        provider: str,
        query_text: str,
        area_id: str = "",
        facet: str = "",
        sort_mode: str = "",
        page: int = 1,
        quota_cost: int = 1,
        next_run_at: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> QueryLedgerRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO query_ledger(
                  id, domain, provider, query_text, area_id, facet, sort_mode, page,
                  quota_cost, next_run_at, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, NULLIF(?, ''), ?, ?, ?, ?, NULLIF(?, ''), ?, ?, ?)
                ON CONFLICT(domain, provider, query_text, facet, sort_mode, page) DO UPDATE SET
                  area_id = excluded.area_id,
                  quota_cost = excluded.quota_cost,
                  next_run_at = excluded.next_run_at,
                  metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    domain,
                    provider,
                    query_text,
                    area_id,
                    facet,
                    sort_mode,
                    page,
                    quota_cost,
                    next_run_at,
                    dumps(metadata or {}),
                    now,
                    now,
                ),
            )
            return optional_record(
                conn.execute(
                    """
                    SELECT * FROM query_ledger
                    WHERE domain = ? AND provider = ? AND query_text = ?
                      AND facet = ? AND sort_mode = ? AND page = ?
                    """,
                    (domain, provider, query_text, facet, sort_mode, page),
                ).fetchone(),
                QueryLedgerRecord,
            )

    def list_due_query_ledger_entries(
        self,
        *,
        domain: str = "",
        provider: str = "",
        due_at: str = "",
        limit: int = 50,
    ) -> list[QueryLedgerRecord]:
        self.init_db()
        due_at = due_at or utc_now()
        sql = """
            SELECT *
            FROM query_ledger
            WHERE (next_run_at IS NULL OR next_run_at = '' OR next_run_at <= ?)
        """
        params: list[Any] = [due_at]
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if provider:
            sql += " AND provider = ?"
            params.append(provider)
        sql += " ORDER BY COALESCE(last_run_at, ''), created_at LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), QueryLedgerRecord)

    def query_ledger_cost_since(self, *, provider: str, since: str) -> int:
        self.init_db()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                  COALESCE((
                    SELECT SUM(quota_cost) FROM query_ledger_runs
                    WHERE provider = ? AND run_at >= ?
                  ), 0) +
                  COALESCE((
                    SELECT SUM(quota_cost) FROM query_ledger q
                    WHERE q.provider = ? AND q.last_run_at >= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM query_ledger_runs r WHERE r.ledger_id = q.id
                      )
                  ), 0) AS cost
                """,
                (provider, since, provider, since),
            ).fetchone()
        return int(row["cost"] or 0)

    def record_query_ledger_result(
        self,
        *,
        ledger_id: str,
        yielded_count: int,
        failure_reason: str = "",
        next_run_at: str = "",
    ) -> QueryLedgerRecord | None:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            previous = conn.execute(
                "SELECT * FROM query_ledger WHERE id = ?",
                (ledger_id,),
            ).fetchone()
            if previous is None:
                return None
            has_runs = conn.execute(
                "SELECT 1 FROM query_ledger_runs WHERE ledger_id = ? LIMIT 1",
                (ledger_id,),
            ).fetchone()
            if previous["last_run_at"] and has_runs is None:
                conn.execute(
                    """
                    INSERT INTO query_ledger_runs(
                      id, ledger_id, provider, quota_cost, status,
                      yielded_count, failure_reason, run_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), ledger_id, previous["provider"],
                        previous["quota_cost"],
                        "failed" if previous["failure_reason"] else "completed",
                        previous["yielded_count"], previous["failure_reason"],
                        previous["last_run_at"],
                    ),
                )
            conn.execute(
                """
                UPDATE query_ledger
                SET yielded_count = ?,
                    failure_reason = ?,
                    last_run_at = ?,
                    next_run_at = NULLIF(?, ''),
                    updated_at = ?
                WHERE id = ?
                """,
                (yielded_count, failure_reason, now, next_run_at, now, ledger_id),
            )
            conn.execute(
                """
                INSERT INTO query_ledger_runs(
                  id, ledger_id, provider, quota_cost, status,
                  yielded_count, failure_reason, run_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()), ledger_id, previous["provider"],
                    previous["quota_cost"], "failed" if failure_reason else "completed",
                    yielded_count, failure_reason, now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM query_ledger WHERE id = ?", (ledger_id,)).fetchone(),
                QueryLedgerRecord,
            )

    def upsert_routine(
        self,
        *,
        routine_key: str,
        title: str,
        description: str = "",
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> RoutineRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO routines(id, routine_key, title, description, enabled, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(routine_key) DO UPDATE SET
                  title = excluded.title,
                  description = excluded.description,
                  enabled = excluded.enabled,
                  metadata_json = excluded.metadata_json,
                  updated_at = excluded.updated_at
                """,
                (str(uuid.uuid4()), routine_key, title, description, 1 if enabled else 0, dumps(metadata or {}), now, now),
            )
            return optional_record(
                conn.execute("SELECT * FROM routines WHERE routine_key = ?", (routine_key,)).fetchone(),
                RoutineRecord,
            )

    def upsert_reminder(
        self,
        *,
        reminder_key: str,
        title: str,
        cadence: str,
        action: str,
        routine_id: str = "",
        schedule: dict[str, Any] | None = None,
        note: str = "",
        requires_confirmation: bool = False,
        enabled: bool = True,
    ) -> ReminderRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reminders(
                  id, routine_id, reminder_key, title, cadence, schedule_json, action,
                  note, requires_confirmation, enabled, created_at, updated_at
                )
                VALUES (?, NULLIF(?, ''), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reminder_key) DO UPDATE SET
                  routine_id = excluded.routine_id,
                  title = excluded.title,
                  cadence = excluded.cadence,
                  schedule_json = excluded.schedule_json,
                  action = excluded.action,
                  note = excluded.note,
                  requires_confirmation = excluded.requires_confirmation,
                  enabled = excluded.enabled,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    routine_id,
                    reminder_key,
                    title,
                    cadence,
                    dumps(schedule or {}),
                    action,
                    note,
                    1 if requires_confirmation else 0,
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM reminders WHERE reminder_key = ?", (reminder_key,)).fetchone(),
                ReminderRecord,
            )

    def get_reminder_by_key(self, *, reminder_key: str) -> ReminderRecord | None:
        self.init_db()
        with self.connect() as conn:
            return optional_record(
                conn.execute(
                    "SELECT * FROM reminders WHERE reminder_key = ?",
                    (reminder_key,),
                ).fetchone(),
                ReminderRecord,
            )

    def list_reminders(self, *, enabled_only: bool = False) -> list[ReminderRecord]:
        self.init_db()
        sql = "SELECT * FROM reminders"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY reminder_key"
        with self.connect() as conn:
            return records(conn.execute(sql), ReminderRecord)

    def delete_reminder(self, *, reminder_key: str) -> bool:
        self.init_db()
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM reminders WHERE reminder_key = ?", (reminder_key,))
            return cursor.rowcount == 1

    def upsert_reminder_event(
        self,
        *,
        reminder_id: str,
        event_key: str,
        due_at: str,
        status: str,
        telegram_message_id: str = "",
        response_payload: dict[str, Any] | None = None,
        sent_at: str = "",
        responded_at: str = "",
    ) -> ReminderEventRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reminder_events(
                  id, reminder_id, event_key, due_at, status, telegram_message_id,
                  response_payload_json, sent_at, responded_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULLIF(?, ''), NULLIF(?, ''), ?, ?)
                ON CONFLICT(event_key) DO UPDATE SET
                  reminder_id = excluded.reminder_id,
                  due_at = excluded.due_at,
                  status = excluded.status,
                  telegram_message_id = excluded.telegram_message_id,
                  response_payload_json = excluded.response_payload_json,
                  sent_at = excluded.sent_at,
                  responded_at = excluded.responded_at,
                  updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    reminder_id,
                    event_key,
                    due_at,
                    status,
                    telegram_message_id,
                    dumps(response_payload or {}),
                    sent_at,
                    responded_at,
                    now,
                    now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM reminder_events WHERE event_key = ?", (event_key,)).fetchone(),
                ReminderEventRecord,
            )

    def create_reminder_event_if_absent(
        self,
        *,
        reminder_id: str,
        event_key: str,
        due_at: str,
        status: str,
        response_payload: dict[str, Any] | None = None,
    ) -> ReminderEventRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reminder_events(
                  id, reminder_id, event_key, due_at, status,
                  response_payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_key) DO NOTHING
                """,
                (
                    str(uuid.uuid4()),
                    reminder_id,
                    event_key,
                    due_at,
                    status,
                    dumps(response_payload or {}),
                    now,
                    now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM reminder_events WHERE event_key = ?", (event_key,)).fetchone(),
                ReminderEventRecord,
            )

    def list_due_reminder_events(
        self,
        *,
        due_at: str,
        status: str = "pending",
        limit: int = 50,
    ) -> list[ReminderEventRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT *
                    FROM reminder_events
                    WHERE status = ? AND due_at <= ?
                    ORDER BY due_at, created_at
                    LIMIT ?
                    """,
                    (status, due_at, limit),
                ),
                ReminderEventRecord,
            )

    def list_reminder_events(
        self,
        *,
        statuses: tuple[str, ...] = (),
        limit: int = 100,
    ) -> list[ReminderEventRecord]:
        self.init_db()
        sql = "SELECT * FROM reminder_events"
        params: list[Any] = []
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            sql += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        sql += " ORDER BY due_at DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), ReminderEventRecord)

    def get_reminder_event(
        self,
        *,
        event_id: str = "",
        event_key: str = "",
    ) -> ReminderEventRecord | None:
        self.init_db()
        if not event_id and not event_key:
            return None
        column, value = ("id", event_id) if event_id else ("event_key", event_key)
        with self.connect() as conn:
            return optional_record(
                conn.execute(f"SELECT * FROM reminder_events WHERE {column} = ?", (value,)).fetchone(),
                ReminderEventRecord,
            )

    def find_reminder_event_by_callback_reference(
        self,
        *,
        callback_kind: str,
        reference: str,
    ) -> ReminderEventRecord | None:
        self.init_db()
        json_key = "legacy_interaction_id" if callback_kind == "interact" else "legacy_confirmation_id"
        event_key = f"honsanam:confirmation:{reference}" if callback_kind == "confirm" else ""
        with self.connect() as conn:
            return optional_record(
                conn.execute(
                    """
                    SELECT *
                    FROM reminder_events
                    WHERE (? != '' AND event_key = ?)
                       OR json_extract(response_payload_json, ?) = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (event_key, event_key, f"$.{json_key}", reference),
                ).fetchone(),
                ReminderEventRecord,
            )

    def update_reminder_event_response(
        self,
        *,
        event_id: str,
        status: str,
        response_payload: dict[str, Any],
        responded_at: str = "",
        telegram_message_id: str | None = None,
        sent_at: str | None = None,
        due_at: str | None = None,
    ) -> ReminderEventRecord | None:
        self.init_db()
        assignments = [
            "status = ?",
            "response_payload_json = ?",
            "responded_at = NULLIF(?, '')",
            "updated_at = ?",
        ]
        params: list[Any] = [status, dumps(response_payload), responded_at, utc_now()]
        if telegram_message_id is not None:
            assignments.append("telegram_message_id = ?")
            params.append(telegram_message_id)
        if sent_at is not None:
            assignments.append("sent_at = NULLIF(?, '')")
            params.append(sent_at)
        if due_at is not None:
            assignments.append("due_at = ?")
            params.append(due_at)
        params.append(event_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE reminder_events SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            return optional_record(
                conn.execute("SELECT * FROM reminder_events WHERE id = ?", (event_id,)).fetchone(),
                ReminderEventRecord,
            )

    def claim_reminder_event(self, *, event_id: str) -> ReminderEventRecord | None:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE reminder_events
                SET status = 'sending', updated_at = ?
                WHERE id = ? AND status IN ('pending', 'failed', 'pending_confirmation')
                """,
                (now, event_id),
            )
            if cursor.rowcount != 1:
                return None
            return optional_record(
                conn.execute("SELECT * FROM reminder_events WHERE id = ?", (event_id,)).fetchone(),
                ReminderEventRecord,
            )

    def create_course_plan(
        self,
        *,
        title: str,
        status: str = "draft",
        area_id: str = "",
        context: dict[str, Any] | None = None,
        generated_at: str = "",
        feedback_summary: str = "",
    ) -> CoursePlanRecord:
        self.init_db()
        plan_id = str(uuid.uuid4())
        generated_at = generated_at or utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO course_plans(
                  id, title, area_id, context_json, status, generated_at, feedback_summary
                )
                VALUES (?, ?, NULLIF(?, ''), ?, ?, ?, ?)
                """,
                (plan_id, title, area_id, dumps(context or {}), status, generated_at, feedback_summary),
            )
            return optional_record(
                conn.execute("SELECT * FROM course_plans WHERE id = ?", (plan_id,)).fetchone(),
                CoursePlanRecord,
            )

    def add_course_plan_stop(
        self,
        *,
        course_plan_id: str,
        stop_order: int,
        source_domain: str,
        title: str,
        reason: str = "",
        place_id: str = "",
        reminder_event_id: str = "",
        archive_item_id: str = "",
        starts_at: str = "",
        evidence_refs: list[str] | None = None,
    ) -> CoursePlanStopRecord:
        self.init_db()
        stop_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO course_plan_stops(
                  id, course_plan_id, stop_order, source_domain, title, place_id,
                  reminder_event_id, archive_item_id, reason, starts_at, evidence_refs_json
                )
                VALUES (?, ?, ?, ?, ?, NULLIF(?, ''), NULLIF(?, ''), NULLIF(?, ''), ?, NULLIF(?, ''), ?)
                """,
                (
                    stop_id,
                    course_plan_id,
                    stop_order,
                    source_domain,
                    title,
                    place_id,
                    reminder_event_id,
                    archive_item_id,
                    reason,
                    starts_at,
                    dumps(evidence_refs or []),
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM course_plan_stops WHERE id = ?", (stop_id,)).fetchone(),
                CoursePlanStopRecord,
            )

    def list_course_plan_stops(self, *, course_plan_id: str) -> list[CoursePlanStopRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT *
                    FROM course_plan_stops
                    WHERE course_plan_id = ?
                    ORDER BY stop_order
                    """,
                    (course_plan_id,),
                ),
                CoursePlanStopRecord,
            )

    def record_user_feedback(
        self,
        *,
        feedback_key: str,
        domain: str,
        action: str,
        place_id: str = "",
        reminder_event_id: str = "",
        recommendation_session_id: str = "",
        course_plan_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> UserFeedbackRecord:
        self.init_db()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_feedback(
                  id, feedback_key, domain, action, place_id, reminder_event_id,
                  recommendation_session_id, course_plan_id, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, NULLIF(?, ''), NULLIF(?, ''), NULLIF(?, ''), NULLIF(?, ''), ?, ?)
                ON CONFLICT(feedback_key) DO UPDATE SET
                  domain = excluded.domain,
                  action = excluded.action,
                  place_id = excluded.place_id,
                  reminder_event_id = excluded.reminder_event_id,
                  recommendation_session_id = excluded.recommendation_session_id,
                  course_plan_id = excluded.course_plan_id,
                  payload_json = excluded.payload_json
                """,
                (
                    str(uuid.uuid4()),
                    feedback_key,
                    domain,
                    action,
                    place_id,
                    reminder_event_id,
                    recommendation_session_id,
                    course_plan_id,
                    dumps(payload or {}),
                    now,
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM user_feedback WHERE feedback_key = ?", (feedback_key,)).fetchone(),
                UserFeedbackRecord,
            )

    def list_user_feedback(
        self,
        *,
        domain: str = "",
        action: str = "",
        limit: int = 50,
    ) -> list[UserFeedbackRecord]:
        self.init_db()
        sql = "SELECT * FROM user_feedback WHERE 1 = 1"
        params: list[Any] = []
        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if action:
            sql += " AND action = ?"
            params.append(action)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), UserFeedbackRecord)

    def create_recommendation_session(
        self,
        *,
        domain: str,
        request_text: str,
        status: str = "completed",
        area_id: str = "",
        context: dict[str, Any] | None = None,
        completed_at: str = "",
    ) -> RecommendationSessionRecord:
        self.init_db()
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO recommendation_sessions(
                  id, domain, request_text, area_id, context_json, status, created_at, completed_at
                )
                VALUES (?, ?, ?, NULLIF(?, ''), ?, ?, ?, NULLIF(?, ''))
                """,
                (session_id, domain, request_text, area_id, dumps(context or {}), status, now, completed_at or now),
            )
            return optional_record(
                conn.execute("SELECT * FROM recommendation_sessions WHERE id = ?", (session_id,)).fetchone(),
                RecommendationSessionRecord,
            )

    def list_recommendation_sessions(
        self,
        *,
        domain: str = "",
        limit: int = 100,
    ) -> list[RecommendationSessionRecord]:
        self.init_db()
        sql = "SELECT * FROM recommendation_sessions"
        params: list[Any] = []
        if domain:
            sql += " WHERE domain = ?"
            params.append(domain)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as conn:
            return records(conn.execute(sql, params), RecommendationSessionRecord)

    def add_recommendation_candidate(
        self,
        *,
        session_id: str,
        evidence_tier: str,
        place_id: str = "",
        rank: int | None = None,
        score: float = 0.0,
        score_breakdown: dict[str, Any] | None = None,
        explanation: str = "",
    ) -> RecommendationCandidateRecord:
        self.init_db()
        candidate_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO recommendation_candidates(
                  id, session_id, place_id, rank, score, score_breakdown_json,
                  evidence_tier, explanation, created_at
                )
                VALUES (?, ?, NULLIF(?, ''), ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    session_id,
                    place_id,
                    rank,
                    score,
                    dumps(score_breakdown or {}),
                    evidence_tier,
                    explanation,
                    utc_now(),
                ),
            )
            return optional_record(
                conn.execute("SELECT * FROM recommendation_candidates WHERE id = ?", (candidate_id,)).fetchone(),
                RecommendationCandidateRecord,
            )

    def list_recommendation_candidates(self, *, session_id: str) -> list[RecommendationCandidateRecord]:
        self.init_db()
        with self.connect() as conn:
            return records(
                conn.execute(
                    """
                    SELECT *
                    FROM recommendation_candidates
                    WHERE session_id = ?
                    ORDER BY rank IS NULL, rank, created_at
                    """,
                    (session_id,),
                ),
                RecommendationCandidateRecord,
            )
