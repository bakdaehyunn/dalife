from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from darchivebot.adapters.food import KakaoFoodApiClient, NaverBlogApiClient

from darchivebot.archive_values import record_to_dict
from darchivebot.domains.course import plan_local_course
from darchivebot.domains.food import (
    FoodCollectionArea,
    FoodCollectionRunner,
    FoodRecommendationContext,
    build_momuk_history_refresh_plan,
    import_momuk_history,
    PlaceRanker,
    build_food_collection_plan,
    parse_food_request,
    persist_food_collection_plan,
    recommend_local_food,
)
from darchivebot.domains.life import (
    FIXED_REMINDER_ORDER,
    LifeValidationError,
    ScheduledReminder,
    add_custom_reminder,
    apply_life_callback,
    default_reminder_config,
    deliver_due_life_reminders,
    due_reminders,
    get_fixed_spec,
    import_honsanam_snapshot,
    kst_datetime,
    load_honsanam_snapshot,
    load_message_pattern,
    preview_due_life_reminders,
    reminder_details,
    reminder_event_details,
    remove_custom_reminder,
    set_reminder_enabled,
    upcoming_reminders,
    update_reminder,
    update_message_pattern,
    validate_stored_reminders,
)
from darchivebot.config import Settings, read_env_values, update_env_values
from darchivebot.persistence.momuk_legacy_reader import read_legacy_momuk_recommendations
from darchivebot.storage import ArchiveStore
from darchivebot.telegram_rooms import read_registered_chat_id


def food_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    action: str,
    area: str,
    aliases: list[str],
    legacy_areas: list[str],
    place_limit: int,
    daily_quota_limit: int,
    default_count: int,
    text: str,
    persist: bool,
    due_at: str,
    limit: int,
    topic: str = "",
    occasion: str = "",
    count: int = 10,
    avoid_terms: list[str] | None = None,
    required_terms: list[str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    max_queries: int = 20,
    max_quota_cost: int = 20,
    dry_run: bool = False,
    source_env: Path | None = None,
    source_root: Path | None = None,
    overwrite: bool = False,
    json_output: bool = False,
) -> int:
    if action == "parse":
        parsed = parse_food_request(text, default_count=default_count)
        payload = {
            "intent": parsed.intent,
            "area": parsed.area,
            "topic": parsed.topic,
            "meal_type": parsed.meal_type,
            "budget": parsed.budget,
            "occasion": parsed.occasion,
            "count": parsed.count,
            "needs_location": parsed.intent == "needs_location",
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(
            f"intent={parsed.intent} area={parsed.area or '-'} topic={parsed.topic or '-'} "
            f"meal_type={parsed.meal_type or '-'} budget={parsed.budget or '-'} "
            f"occasion={parsed.occasion or '-'} count={parsed.count}"
        )
        return 0

    if action == "plan-collection":
        plan = build_food_collection_plan(
            areas=[FoodCollectionArea(area, aliases=tuple(aliases))],
            daily_quota_limit=daily_quota_limit,
        )
        entries = []
        if persist:
            stored_area = store.upsert_area(name=area, normalized_name=area.lower().replace(" ", ""))
            entries = persist_food_collection_plan(store, plan, area_ids_by_name={area: stored_area["id"]})
        payload = {
            "area": area,
            "aliases": aliases,
            "daily_quota_limit": daily_quota_limit,
            "quota_cost": plan.quota_cost,
            "queries": [query.__dict__ | {"facet": query.facet.value} for query in plan.queries],
            "persisted": [record_to_dict(row) for row in entries],
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(f"food collection plan area={area} queries={len(plan.queries)} quota_cost={plan.quota_cost}")
        for query in plan.queries:
            print(f"{query.provider}\t{query.facet.value}\t{query.sort_mode}\t{query.query_text}")
        if persist:
            print(f"persisted query_ledger entries={len(entries)}")
        return 0

    if action == "plan-history-refresh":
        plan = build_momuk_history_refresh_plan(
            store,
            area=area,
            legacy_areas=tuple(legacy_areas),
            place_limit=max(0, place_limit),
        )
        entries = []
        if persist:
            stored_area = store.upsert_area(name=area, normalized_name=area.lower().replace(" ", ""))
            entries = persist_food_collection_plan(store, plan, area_ids_by_name={area: stored_area["id"]})
        payload = {
            "area": area,
            "legacy_areas": legacy_areas,
            "place_count": len(plan.queries) // 2,
            "quota_cost": plan.quota_cost,
            "queries": [query.__dict__ | {"facet": query.facet.value} for query in plan.queries],
            "persisted": len(entries),
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"history refresh area={area} places={payload['place_count']} "
                f"queries={len(plan.queries)} persisted={len(entries)}"
            )
            for query in plan.queries:
                print(f"{query.provider}\t{query.query_text}")
        return 0

    if action == "due-queries":
        rows = store.list_due_query_ledger_entries(domain="food", due_at=due_at, limit=limit)
        if json_output:
            print(json.dumps([record_to_dict(row) for row in rows], ensure_ascii=False, indent=2))
            return 0
        if not rows:
            print("no due food queries")
            return 0
        for row in rows:
            print(f"{row['id']}\t{row['provider']}\t{row['facet']}\tcost={row['quota_cost']}\t{row['query_text']}")
        return 0

    if action == "run-collection":
        runner = FoodCollectionRunner(
            store,
            kakao=KakaoFoodApiClient(settings.kakao_rest_api_key),
            naver=NaverBlogApiClient(
                settings.naver_client_id,
                settings.naver_client_secret,
                allowed_domains=settings.food_blog_allowed_domains,
            ),
            provider_daily_limits={
                "kakao_local": settings.kakao_daily_soft_limit,
                "naver_blog": settings.naver_daily_soft_limit,
            },
        )
        run = runner.run_due(
            max_queries=max(0, max_queries),
            max_quota_cost=max(0, max_quota_cost),
            dry_run=dry_run,
        )
        payload = {
            "dry_run": dry_run,
            "items": [asdict(item) for item in run.items],
            "skipped_unconfigured": list(run.skipped_unconfigured),
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0 if not any(item.status == "failed" for item in run.items) else 1
        if not run.items:
            suffix = (
                f"; unconfigured={','.join(run.skipped_unconfigured)}"
                if run.skipped_unconfigured
                else ""
            )
            print(f"no runnable food collection queries{suffix}")
            return 0
        for item in run.items:
            print(
                f"{item.status}\t{item.provider}\tyield={item.yielded_count}\t"
                f"places={item.places_stored}\tevidence={item.evidence_stored}\t"
                f"links={item.evidence_links}\t{item.query_text}"
            )
        return 0 if not any(item.status == "failed" for item in run.items) else 1

    if action == "quota":
        since = datetime.now(datetime_timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        providers = (
            ("kakao_local", bool(settings.kakao_rest_api_key), settings.kakao_daily_soft_limit),
            (
                "naver_blog",
                bool(settings.naver_client_id and settings.naver_client_secret),
                settings.naver_daily_soft_limit,
            ),
        )
        payload = []
        for provider, configured, soft_limit in providers:
            used = store.query_ledger_cost_since(provider=provider, since=since)
            payload.append(
                {
                    "provider": provider,
                    "configured": configured,
                    "date": since[:10],
                    "used": used,
                    "soft_limit": soft_limit,
                    "remaining": max(0, soft_limit - used),
                }
            )
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for item in payload:
                print(
                    f"provider={item['provider']} configured={str(item['configured']).lower()} "
                    f"date={item['date']} count={item['used']} "
                    f"soft_limit={item['soft_limit']} remaining={item['remaining']}"
                )
        return 0

    if action == "import-provider-config":
        if source_env is None:
            raise ValueError("source env is required")
        source = read_env_values(source_env)
        target_path = settings.root / ".env"
        target = read_env_values(target_path)
        mapping = {
            "KAKAO_REST_API_KEY": "KAKAO_REST_API_KEY",
            "NAVER_CLIENT_ID": "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET": "NAVER_CLIENT_SECRET",
            "NAVER_DAILY_SOFT_LIMIT": "DARCHIVE_NAVER_DAILY_SOFT_LIMIT",
            "BLOG_ALLOWED_DOMAINS": "DARCHIVE_FOOD_BLOG_ALLOWED_DOMAINS",
        }
        updates = {
            target_key: source[source_key]
            for source_key, target_key in mapping.items()
            if source.get(source_key) and (overwrite or not target.get(target_key))
        }
        if not dry_run and updates:
            update_env_values(target_path, updates)
        payload = {
            "source_env": str(source_env.expanduser().resolve()),
            "target_env": str(target_path.resolve()),
            "dry_run": dry_run,
            "imported_keys": sorted(updates),
            "missing_source_keys": sorted(
                target_key for source_key, target_key in mapping.items() if not source.get(source_key)
            ),
            "preserved_keys": sorted(
                target_key
                for source_key, target_key in mapping.items()
                if source.get(source_key) and target.get(target_key) and not overwrite
            ),
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            mode = "would import" if dry_run else "imported"
            print(f"{mode} provider config keys: {', '.join(payload['imported_keys']) or 'none'}")
        return 0

    if action == "import-momuk-history":
        if source_root is None:
            raise ValueError("source root is required")
        source_db = source_root.expanduser().resolve() / ".local/state/momukbot.sqlite3"
        report = import_momuk_history(
            store,
            read_legacy_momuk_recommendations(source_db),
            dry_run=dry_run,
        )
        payload = asdict(report) | {"source_db": str(source_db)}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            mode = "would import" if dry_run else "imported"
            print(
                f"{mode} Momuk history rows={report.imported_rows} "
                f"sessions={report.sessions} candidates={report.candidates} "
                f"linked_places={report.linked_places} skipped={report.skipped_rows}"
            )
        return 0

    if action == "recommend-local":
        request_text = " ".join(part for part in (area, topic, occasion, "추천") if part)
        result = recommend_local_food(
            store,
            request_text=request_text,
            context=FoodRecommendationContext(
                area=area,
                topic=topic,
                occasion=occasion,
                count=count,
                latitude=latitude,
                longitude=longitude,
                avoid_terms=tuple(avoid_terms or ()),
                required_terms=tuple(required_terms or ()),
            ),
            persist_session=not dry_run,
        )
        payload = {
            "area": area,
            "topic": topic,
            "occasion": occasion,
            "requested_count": count,
            "returned_count": len(result.ranked_places),
            "session_id": result.session_id,
            "places": [
                {
                    "rank": index,
                    "place_id": ranked.place.place_id,
                    "name": ranked.place.name,
                    "category": ranked.place.category,
                    "address": ranked.place.address,
                    "map_url": ranked.place.map_url,
                    "score": ranked.score,
                    "score_breakdown": ranked.breakdown,
                    "evidence_tier": ranked.place.evidence_tier.value,
                    "evidence": [
                        {
                            "provider": evidence.provider,
                            "url": evidence.url,
                            "title": evidence.title,
                            "author": evidence.author,
                            "published_at": evidence.published_at,
                            "score": evidence.score,
                        }
                        for evidence in ranked.place.evidence
                    ],
                }
                for index, ranked in enumerate(result.ranked_places, start=1)
            ],
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if result.area is None:
            print(f"no local food area: {area}")
            return 0
        if not result.ranked_places:
            print(f"no local food candidates for {area}")
            return 0
        print(
            f"local food recommendations area={area} "
            f"returned={len(result.ranked_places)}/{count} session={result.session_id}"
        )
        for index, ranked in enumerate(result.ranked_places, start=1):
            print(
                f"{index}. {ranked.place.name}\t{ranked.place.category}\t"
                f"score={ranked.score:.4f}\tevidence={ranked.place.evidence_tier.value}"
            )
            if ranked.place.map_url:
                print(f"   map: {ranked.place.map_url}")
            for evidence in ranked.place.evidence[:2]:
                print(f"   evidence: {evidence.url}")
        return 0

    raise ValueError(f"unsupported food action: {action}")


def life_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    action: str,
    date_text: str = "",
    time_text: str = "",
    days: int = 7,
    source_root: Path | None = None,
    reminder_id: str = "",
    add_kind: str = "",
    title: str | None = None,
    reminder_kind: str | None = None,
    reminder_time: str | None = None,
    reminder_action: str | None = None,
    note: str | None = None,
    reminder_date: str | None = None,
    weekday: str | None = None,
    base_date: str | None = None,
    interval_days: int | None = None,
    confirmation_id: str = "",
    confirmation_answer: str = "",
    pattern_action: str = "",
    pattern_prefix: str | None = None,
    pattern_schedule_label: str | None = None,
    pattern_action_label: str | None = None,
    pattern_note_label: str | None = None,
    dry_run: bool = False,
    json_output: bool,
    api_factory: Any,
) -> int:
    if action == "list":
        stored = store.list_reminders()
        if stored:
            payload = [reminder_details(row) for row in stored]
            if json_output:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for item in payload:
                    print(f"{item['id']}\t{item['type']}\t{item['title']}\tenabled={str(item['enabled']).lower()}")
            return 0
        payload = [
            {
                "reminder_id": spec.reminder_id,
                "title": spec.title,
                "schedule_kind": spec.schedule_kind,
                "default_action": spec.default_action,
                "requires_confirmation": spec.requires_confirmation,
                "interaction_labels": [
                    {"label": label, "choice": choice}
                    for label, choice in spec.interaction_labels
                ],
            }
            for spec in (get_fixed_spec(reminder_id) for reminder_id in FIXED_REMINDER_ORDER)
        ]
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        for item in payload:
            confirmation = " confirmation=yes" if item["requires_confirmation"] else ""
            print(
                f"{item['reminder_id']}\t{item['schedule_kind']}\t"
                f"{item['title']}\t{item['default_action']}{confirmation}"
            )
        return 0

    if action == "show":
        row = store.get_reminder_by_key(reminder_key=reminder_id)
        if row is None:
            print(f"[FAIL] unknown reminder: {reminder_id}")
            return 1
        payload = reminder_details(row)
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0

    if action in {"enable", "disable"}:
        try:
            set_reminder_enabled(store, reminder_id, action == "enable")
        except LifeValidationError as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"updated {reminder_id}")
        return 0

    if action == "remove":
        try:
            remove_custom_reminder(store, reminder_id)
        except LifeValidationError as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"removed {reminder_id}")
        return 0

    if action == "add":
        if add_kind != "custom":
            raise ValueError(f"unsupported life add kind: {add_kind}")
        values = {
            "id": reminder_id,
            "title": title,
            "kind": reminder_kind,
            "time": reminder_time,
            "action": reminder_action,
            "note": note or "",
            "date": reminder_date,
            "weekday": weekday,
            "base_date": base_date,
            "days": interval_days,
        }
        try:
            add_custom_reminder(store, values)
        except (LifeValidationError, TypeError, ValueError) as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"added {reminder_id}")
        return 0

    if action == "update":
        values = {
            "title": title,
            "time": reminder_time,
            "action": reminder_action,
            "note": note,
            "date": reminder_date,
            "weekday": weekday,
            "base_date": base_date,
            "days": interval_days,
        }
        try:
            update_reminder(store, reminder_id, values)
        except (LifeValidationError, TypeError, ValueError) as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"updated {reminder_id}")
        return 0

    if action == "validate":
        errors = validate_stored_reminders(store)
        if errors:
            for error in errors:
                print(f"[FAIL] {error}")
            return 1
        print("reminder definitions valid")
        return 0

    if action in {"pending", "interactions"}:
        statuses = (
            ("pending_confirmation",)
            if action == "pending"
            else ("responded", "completed", "deferred")
        )
        payload = [
            reminder_event_details(row)
            for row in store.list_reminder_events(statuses=statuses, limit=100)
        ]
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif not payload:
            print("No pending confirmations." if action == "pending" else "No interactions.")
        else:
            for item in payload:
                print(
                    f"{item['id']}\t{item['status']}\t{item['due_at']}\t"
                    f"{item['title'] or item['event_key']}\t{item['selected_response'] or '-'}"
                )
        return 0

    if action == "answer":
        event = store.get_reminder_event(event_id=confirmation_id)
        if event is None:
            event = store.find_reminder_event_by_callback_reference(
                callback_kind="confirm",
                reference=confirmation_id,
            )
        if event is None or event["status"] != "pending_confirmation":
            print(f"[FAIL] unknown pending confirmation: {confirmation_id}")
            return 1
        callback_data = (
            f"life:{confirmation_id}:{confirmation_answer}"
            if str(event["id"]) == confirmation_id
            else f"confirm:{confirmation_id}:{confirmation_answer}"
        )
        result = apply_life_callback(
            store,
            callback_data,
            responded_at=datetime.now(ZoneInfo(settings.life_timezone)).isoformat(timespec="seconds"),
        )
        if result is None:
            print(f"[FAIL] unknown pending confirmation: {confirmation_id}")
            return 1
        print(f"recorded {confirmation_answer} for {confirmation_id}")
        return 0

    if action == "pattern":
        try:
            pattern = (
                load_message_pattern(store)
                if pattern_action == "show"
                else update_message_pattern(
                    store,
                    prefix=pattern_prefix,
                    schedule_label=pattern_schedule_label,
                    action_label=pattern_action_label,
                    note_label=pattern_note_label,
                )
            )
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(json.dumps(asdict(pattern), ensure_ascii=False, indent=2))
        return 0

    if action == "preview":
        reminders = due_reminders(
            kst_datetime(date_text, time_text, settings.life_timezone),
            default_reminder_config(),
            pattern=load_message_pattern(store),
        )
        return _print_life_reminders(reminders, json_output=json_output, empty_message="no due life reminders")

    if action == "next":
        reminders = upcoming_reminders(
            kst_datetime(date_text, time_text, settings.life_timezone),
            default_reminder_config(),
            days=days,
            pattern=load_message_pattern(store),
        )
        return _print_life_reminders(reminders, json_output=json_output, empty_message="no upcoming life reminders")

    if action == "run-once":
        now = _life_run_time(date_text, time_text, timezone=settings.life_timezone)
        reminders = preview_due_life_reminders(store, now)
        if dry_run:
            payload = {
                "dry_run": True,
                "at": now.isoformat(),
                "due": len(reminders),
                "sent": 0,
                "reminders": [
                    {
                        "reminder_id": item.reminder_id,
                        "scheduled_at": item.scheduled_at.isoformat(),
                        "title": item.title,
                    }
                    for item in reminders
                ],
            }
            if json_output:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            elif reminders:
                _print_life_reminders(reminders, json_output=False, empty_message="No reminders due.")
            else:
                print("No reminders due.")
            return 0
        chat_id = read_registered_chat_id(settings)
        if not chat_id and len(settings.telegram_allowed_chat_ids) == 1:
            chat_id = settings.telegram_allowed_chat_ids[0]
        if not settings.telegram_bot_token:
            print("[FAIL] TELEGRAM_BOT_TOKEN is not configured")
            return 1
        if not chat_id:
            print("[FAIL] no registered or uniquely allowed Telegram chat is configured")
            return 1
        report = deliver_due_life_reminders(
            store,
            api_factory(settings.telegram_bot_token),
            chat_id=chat_id,
            now=now,
        )
        payload = asdict(report) | {"dry_run": False, "at": now.isoformat()}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"life reminders due={report.due} sent={report.sent} "
                f"failed={report.failed} skipped={report.skipped}"
            )
        return 1 if report.failed else 0

    if action == "import-honsanam":
        if source_root is None:
            raise ValueError("source root is required")
        snapshot = load_honsanam_snapshot(source_root)
        report = import_honsanam_snapshot(store, snapshot, dry_run=dry_run)
        payload = asdict(report) | {"source_root": str(snapshot.root)}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        mode = "dry-run" if report.dry_run else "imported"
        print(
            f"honsanam {mode} reminders={report.reminders} sent={report.sent_events} "
            f"interactions={report.interaction_events} confirmations={report.confirmation_events}"
        )
        return 0

    raise ValueError(f"unsupported life action: {action}")


def _life_run_time(date_text: str, time_text: str, *, timezone: str = "Asia/Seoul") -> datetime:
    if bool(date_text) != bool(time_text):
        raise ValueError("--date and --time must be provided together")
    if date_text:
        return kst_datetime(date_text, time_text, timezone)
    return datetime.now(ZoneInfo(timezone)).replace(second=0, microsecond=0)


def _print_life_reminders(reminders: list[ScheduledReminder], *, json_output: bool, empty_message: str) -> int:
    payload = [
        {
            "reminder_id": reminder.reminder_id,
            "scheduled_at": reminder.scheduled_at.isoformat(),
            "title": reminder.title,
            "message": reminder.message,
            "sent_key": reminder.sent_key,
        }
        for reminder in reminders
    ]
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not reminders:
        print(empty_message)
        return 0
    for reminder in reminders:
        print(f"{reminder.reminder_id}\t{reminder.scheduled_at.isoformat()}\t{reminder.title}")
    return 0


def course_cmd(
    store: ArchiveStore,
    *,
    action: str,
    title: str,
    area: str,
    date_text: str,
    time_text: str,
    persist: bool,
    json_output: bool,
) -> int:
    if action != "plan":
        raise ValueError(f"unsupported course action: {action}")
    result = plan_local_course(
        store,
        title=title,
        area_name=area,
        generated_at=kst_datetime(date_text, time_text),
        intent=f"{area} course",
        persist=persist,
    )
    plan = result.plan
    stored = result.stored
    payload = {
        "title": plan.title,
        "generated_at": plan.generated_at.isoformat(),
        "context": plan.context,
        "stops": [stop.__dict__ | {"starts_at": stop.starts_at.isoformat() if stop.starts_at else None} for stop in plan.stops],
        "stored": record_to_dict(stored) if stored else None,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"course plan title={plan.title} stops={len(plan.stops)}")
    if stored:
        print(f"stored course_plan_id={stored['id']}")
    return 0
