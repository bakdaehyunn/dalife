from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone as datetime_timezone
from typing import Any
from zoneinfo import ZoneInfo

from dalife.adapters.food import KakaoFoodApiClient, NaverBlogApiClient

from dalife.archive_values import record_to_dict
from dalife.domains.course import plan_local_course
from dalife.domains.food import (
    FoodCollectionArea,
    FoodCollectionRunner,
    FoodRecommendationContext,
    PlaceRanker,
    build_food_collection_plan,
    parse_food_request,
    persist_food_collection_plan,
    recommend_local_food,
    build_preference_profile,
    collection_report,
    evaluate_recommendations,
    persist_preference_profile,
    zone_coverage,
)
from dalife.domains.life import (
    FIXED_REMINDER_ORDER,
    LifeValidationError,
    ScheduledReminder,
    add_custom_reminder,
    apply_life_callback,
    default_reminder_config,
    deliver_due_life_reminders,
    due_reminders,
    get_fixed_spec,
    kst_datetime,
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
from dalife.config import Settings
from dalife.storage import ArchiveStore
from dalife.telegram_rooms import read_registered_chat_id
from dalife.telegram_api import TelegramApiClient
from dalife.telegram_food import send_due_food_visit_followups


def food_cmd(
    settings: Settings,
    store: ArchiveStore,
    *,
    action: str,
    area: str,
    aliases: list[str],
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
    zone_action: str = "",
    zone_name: str = "",
    zone_kind: str = "activity",
    zone_areas: list[str] | None = None,
    zone_radius_meters: int = 0,
    walk_minutes: int | None = None,
    transit_minutes: int | None = None,
    taxi_minutes: int | None = None,
    priority: int = 0,
    days: int = 30,
    profile_action: str = "",
    feedback_action: str = "",
    place_id: str = "",
    session_id: str = "",
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
        local_now = datetime.now(ZoneInfo(settings.life_timezone))
        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = local_midnight.astimezone(datetime_timezone.utc).isoformat()
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
                    "date": local_midnight.date().isoformat(),
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

    if action == "collection-report":
        payload = collection_report(store, days=max(1, days))
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"collection report days={payload['days']} runs={payload['runs']}")
            for item in payload["groups"]:
                print(
                    f"{item['area']}\t{item['provider']}\t{item['facet']}\t"
                    f"runs={item['runs']} utility={item['utility_score']} "
                    f"novelty={item['novelty_rate']} duplicates={item['duplicate_rate']}"
                )
        return 0

    if action == "zones":
        if zone_action == "add":
            zone = store.upsert_mobility_zone(
                name=zone_name,
                kind=zone_kind,
                center_latitude=float(latitude),
                center_longitude=float(longitude),
                radius_meters=zone_radius_meters,
                walk_minutes=walk_minutes,
                transit_minutes=transit_minutes,
                taxi_minutes=taxi_minutes,
                priority=priority,
            )
            linked_areas = []
            for area_name in zone_areas or []:
                stored_area = store.get_area_by_normalized_name(
                    normalized_name=area_name.lower().replace(" ", "")
                )
                if stored_area:
                    store.link_mobility_zone_area(zone_id=zone["id"], area_id=stored_area["id"])
                    linked_areas.append(area_name)
            payload = record_to_dict(zone) | {"areas": linked_areas}
        elif zone_action == "disable":
            payload = {"name": zone_name, "disabled": store.set_mobility_zone_enabled(name=zone_name, enabled=False)}
        else:
            zones = store.list_mobility_zones(enabled_only=zone_action != "list")
            if zone_name:
                zones = [zone for zone in zones if zone["name"] == zone_name]
            payload = [
                record_to_dict(zone) | {"coverage": asdict(zone_coverage(store, zone))}
                for zone in zones
            ]
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if isinstance(payload, list):
                for item in payload:
                    coverage = item["coverage"]
                    print(
                        f"{item['name']}\t{item['kind']}\tradius={item['radius_meters']}m\t"
                        f"inside={coverage['inside_count']} evidence={coverage['evidence_coverage']:.1%}"
                    )
            else:
                print(json.dumps(payload, ensure_ascii=False))
        return 0

    if action == "profile":
        if profile_action == "rebuild":
            snapshot = persist_preference_profile(store)
            payload = record_to_dict(snapshot)
            payload["features"] = json.loads(payload.pop("features_json"))
        else:
            payload = build_preference_profile(store)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else json.dumps(payload, ensure_ascii=False))
        return 0

    if action == "feedback":
        key = f"cli:{feedback_action}:{place_id}:{datetime.now(datetime_timezone.utc).isoformat()}"
        row = store.record_user_feedback(
            feedback_key=key,
            domain="food",
            action=feedback_action,
            place_id=place_id,
            recommendation_session_id=session_id,
            payload={"source": "cli"},
        )
        payload = record_to_dict(row)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else f"recorded {feedback_action} for {place_id}")
        return 0

    if action == "evaluate":
        payload = evaluate_recommendations(store, limit=max(1, limit))
        print(json.dumps(payload, ensure_ascii=False, indent=2) if json_output else json.dumps(payload, ensure_ascii=False))
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
        food_due = store.list_due_food_visit_followups(
            due_at=now.astimezone(datetime_timezone.utc).isoformat(),
            limit=20,
        )
        if dry_run:
            payload = {
                "dry_run": True,
                "at": now.isoformat(),
                "due": len(reminders),
                "sent": 0,
                "food_followups_due": len(food_due),
                "food_followups_sent": 0,
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
        api = api_factory(settings.telegram_bot_token)
        report = deliver_due_life_reminders(
            store,
            api,
            chat_id=chat_id,
            now=now,
        )
        food_report = send_due_food_visit_followups(
            store,
            api,
            default_chat_id=chat_id,
            now=now.astimezone(datetime_timezone.utc),
        )
        payload = asdict(report) | {
            "dry_run": False,
            "at": now.isoformat(),
            "food_followups_due": food_report["due"],
            "food_followups_sent": food_report["sent"],
        }
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"life reminders due={report.due} sent={report.sent} "
                f"failed={report.failed} skipped={report.skipped}; "
                f"food followups due={food_report['due']} sent={food_report['sent']}"
            )
        return 1 if report.failed else 0

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
