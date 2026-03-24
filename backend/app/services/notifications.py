import threading
from contextlib import suppress
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import NotificationDelivery, NotificationOutbox, PortalUser, PortalUserSubscription, utcnow
from .account_access import get_active_admin_user_ids, resolve_portal_access
from .historical_intelligence import normalize_major_code, normalize_major_name, normalize_school_name
from .nlp import keyword_matches_content, normalize_tag
from .sse_manager import manager as sse_manager

with suppress(Exception):
    import ahocorasick  # type: ignore


class NotificationMatcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded_signature: str | None = None
        self._last_checked_at = utcnow() - timedelta(days=365)
        self._school_rules: list[tuple[str, str, str]] = []
        self._major_rules: list[tuple[str, str, str]] = []
        self._region_rules: list[tuple[str, str, str]] = []
        self._radar_rules: list[tuple[str, str, str | None, str | None, str]] = []
        self._keyword_rules: list[tuple[str, str, str]] = []
        self._keyword_rule_map: dict[str, list[tuple[str, str, str]]] = {}
        self._keyword_automaton = None

    def refresh_if_needed(self, db: Session, *, force: bool = False) -> None:
        settings = get_settings()
        now = utcnow()
        if not force and (now - self._last_checked_at).total_seconds() < settings.notification_cache_refresh_seconds:
            return

        admin_user_ids = get_active_admin_user_ids(db)
        self._recycle_expired_premium_users(db, admin_user_ids=admin_user_ids)
        premium_user_ids = {
            user.id
            for user in db.query(PortalUser).filter(PortalUser.status == "active").all()
            if resolve_portal_access(db, user).is_premium
        }
        school_allowed_user_ids = premium_user_ids | admin_user_ids

        stats = (
            db.query(
                func.count(PortalUserSubscription.id),
                func.max(PortalUserSubscription.updated_at),
            )
            .filter(PortalUserSubscription.status == "active")
            .one()
        )
        total = int(stats[0] or 0)
        max_updated = stats[1].isoformat() if stats[1] else "none"
        signature = f"{total}:{max_updated}"

        self._last_checked_at = now
        if not force and signature == self._loaded_signature:
            return

        rows = (
            db.query(PortalUserSubscription)
            .filter(PortalUserSubscription.status == "active")
            .order_by(PortalUserSubscription.updated_at.desc())
            .all()
        )
        school_rules: list[tuple[str, str, str]] = []
        major_rules: list[tuple[str, str, str]] = []
        region_rules: list[tuple[str, str, str]] = []
        radar_rules: list[tuple[str, str, str | None, str | None, str]] = []
        keyword_rules: list[tuple[str, str, str]] = []
        keyword_rule_map: dict[str, list[tuple[str, str, str]]] = {}

        for row in rows:
            value = (row.value or "").strip().lower()
            if not value:
                continue
            category = (row.category or "all").strip().lower() or "all"
            rule = (row.user_id, value, category)
            if row.subscription_type == "school":
                if row.user_id not in school_allowed_user_ids:
                    continue
                school_rules.append(rule)
            elif row.subscription_type == "radar":
                school_name_normalized = normalize_school_name(row.target_school_name or row.value)
                major_code = normalize_major_code(row.target_major_code)
                major_name = normalize_major_name(row.target_major_name)
                if not school_name_normalized or (not major_code and not major_name):
                    continue
                radar_rules.append((row.user_id, school_name_normalized, major_code, major_name, category))
            elif row.subscription_type == "major":
                major_rules.append(rule)
            elif row.subscription_type == "region":
                region_rules.append(rule)
            else:
                keyword_rules.append(rule)
                keyword_rule_map.setdefault(value, []).append(rule)

        keyword_automaton = None
        if "ahocorasick" in globals() and keyword_rule_map:
            keyword_automaton = ahocorasick.Automaton()  # type: ignore[name-defined]
            for value in keyword_rule_map.keys():
                keyword_automaton.add_word(value, value)
            keyword_automaton.make_automaton()

        with self._lock:
            self._school_rules = school_rules
            self._major_rules = major_rules
            self._region_rules = region_rules
            self._radar_rules = radar_rules
            self._keyword_rules = keyword_rules
            self._keyword_rule_map = keyword_rule_map
            self._keyword_automaton = keyword_automaton
            self._loaded_signature = signature

    def reset(self) -> None:
        with self._lock:
            self._loaded_signature = None
            self._last_checked_at = utcnow() - timedelta(days=365)
            self._school_rules = []
            self._major_rules = []
            self._region_rules = []
            self._radar_rules = []
            self._keyword_rules = []
            self._keyword_rule_map = {}
            self._keyword_automaton = None

    def match_user_ids(self, payload: dict[str, Any]) -> set[str]:
        category = str(payload.get("category") or "").strip().lower()
        school_name = str(payload.get("school_name") or "").strip()
        normalized_school_name = normalize_school_name(school_name) if school_name else ""
        major = str(payload.get("major") or payload.get("major_name") or "").strip()
        normalized_major_name = normalize_major_name(major) or ""
        normalized_major_code = normalize_major_code(payload.get("major_code")) or ""
        region = str(payload.get("region") or "").strip().lower()
        raw_tags = [
            *list(payload.get("tags") or []),
            *list(payload.get("system_tags") or []),
            str(payload.get("channel_label") or ""),
        ]
        tags = [normalize_tag(tag) for tag in raw_tags]
        tags = [tag for tag in tags if tag]
        full_text = " ".join(
            x
            for x in [
                str(payload.get("title") or "").strip().lower(),
                str(payload.get("summary") or "").strip().lower(),
                str(payload.get("body") or "").strip().lower(),
                school_name.lower(),
                major.lower(),
                normalized_major_code,
                str(payload.get("department_name") or "").strip().lower(),
                str(payload.get("channel_label") or "").strip().lower(),
                region,
            ]
            if x
        )

        with self._lock:
            school_rules = list(self._school_rules)
            major_rules = list(self._major_rules)
            region_rules = list(self._region_rules)
            radar_rules = list(self._radar_rules)
            keyword_rules = list(self._keyword_rules)
            keyword_rule_map = dict(self._keyword_rule_map)
            keyword_automaton = self._keyword_automaton

        matched_user_ids: set[str] = set()
        for user_id, value, rule_category in school_rules:
            if value in school_name.lower() and self._category_match(category, rule_category):
                matched_user_ids.add(user_id)

        for user_id, value, rule_category in major_rules:
            if not self._category_match(category, rule_category):
                continue
            if value in major.lower() or (normalized_major_code and value in normalized_major_code.lower()):
                matched_user_ids.add(user_id)

        for user_id, value, rule_category in region_rules:
            if value in region and self._category_match(category, rule_category):
                matched_user_ids.add(user_id)

        for user_id, school_value, major_code, major_name, rule_category in radar_rules:
            if not self._category_match(category, rule_category):
                continue
            if school_value != normalized_school_name:
                continue
            if major_code and major_code == normalized_major_code:
                matched_user_ids.add(user_id)
                continue
            if major_name and normalized_major_name and major_name == normalized_major_name:
                matched_user_ids.add(user_id)

        if keyword_automaton is not None:
            seen_keywords: set[str] = set()
            for _, keyword in keyword_automaton.iter(full_text):
                if keyword in seen_keywords:
                    continue
                seen_keywords.add(keyword)
                for user_id, _, rule_category in keyword_rule_map.get(keyword, []):
                    if self._category_match(category, rule_category):
                        matched_user_ids.add(user_id)
        for user_id, value, rule_category in keyword_rules:
            if not self._category_match(category, rule_category):
                continue
            if keyword_matches_content(value, full_text, tags):
                matched_user_ids.add(user_id)

        return matched_user_ids

    @staticmethod
    def _category_match(content_category: str, rule_category: str) -> bool:
        return rule_category == "all" or rule_category == content_category

    @staticmethod
    def _recycle_expired_premium_users(db: Session, *, admin_user_ids: set[str]) -> None:
        rows = db.query(PortalUser).filter(PortalUser.status == "active").all()
        expired_user_ids = []
        for row in rows:
            if row.id in admin_user_ids:
                continue
            state = resolve_portal_access(db, row)
            if state.expired_premium and not state.is_premium:
                expired_user_ids.append(row.id)
        if not expired_user_ids:
            return

        subscriptions = (
            db.query(PortalUserSubscription)
            .filter(
                PortalUserSubscription.user_id.in_(expired_user_ids),
                PortalUserSubscription.subscription_type == "school",
                PortalUserSubscription.status == "active",
            )
            .all()
        )
        for sub in subscriptions:
            sub.status = "deleted"
        db.commit()


class NotificationEngine:
    def __init__(self) -> None:
        self._matcher = NotificationMatcher()

    def process_batch(self) -> int:
        return self.process_outbox_batch() + self.process_delivery_batch()

    def process_outbox_batch(self) -> int:
        settings = get_settings()
        locked_ids = self._lock_pending_rows(settings.notification_batch_size)
        if not locked_ids:
            return 0

        processed = 0
        for outbox_id in locked_ids:
            with SessionLocal() as db:
                outbox = db.query(NotificationOutbox).filter(NotificationOutbox.id == outbox_id).one_or_none()
                if outbox is None:
                    continue
                try:
                    payload = dict(outbox.payload or {})
                    user_ids = self._resolve_outbox_user_ids(db, outbox=outbox, payload=payload)
                    inapp_deliveries = self._enqueue_deliveries(
                        db,
                        outbox_id=outbox.id,
                        payload=payload,
                        user_ids=user_ids,
                    )

                    outbox.status = "done"
                    outbox.processed_at = utcnow()
                    outbox.processing_started_at = None
                    outbox.last_error = None
                    db.flush()
                    dispatch_cutoff = utcnow()
                    realtime_items = [
                        (row.user_id, self._serialize_delivery_item(row))
                        for row in inapp_deliveries
                        if row.deliver_after <= dispatch_cutoff
                    ]
                    db.commit()
                    self._push_live_inapp_items(realtime_items)
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    self._handle_outbox_error(outbox_id, str(exc))
        return processed

    def _resolve_outbox_user_ids(self, db: Session, *, outbox: NotificationOutbox, payload: dict[str, Any]) -> set[str]:
        if (outbox.event_type or "").strip().lower() == "monitor.hit":
            user_id = str(payload.get("user_id") or "").strip()
            return {user_id} if user_id else set()

        self._matcher.refresh_if_needed(db)
        return self._matcher.match_user_ids(payload)

    def process_delivery_batch(self) -> int:
        settings = get_settings()
        locked_ids = self._lock_pending_delivery_rows(settings.notification_batch_size)
        if not locked_ids:
            return 0

        processed = 0
        for delivery_id in locked_ids:
            with SessionLocal() as db:
                delivery = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).one_or_none()
                if delivery is None:
                    continue
                try:
                    self._deliver_external_notification(delivery)
                    delivery.status = "sent"
                    delivery.sent_at = utcnow()
                    delivery.processing_started_at = None
                    delivery.last_error = None
                    db.commit()
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    self._handle_delivery_error(delivery_id, str(exc))
                    processed += 1
        return processed

    def fetch_and_mark_user_deliveries(self, user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = (
                db.query(NotificationDelivery)
                .filter(
                    NotificationDelivery.user_id == user_id,
                    NotificationDelivery.channel == "inapp",
                    NotificationDelivery.status == "pending",
                    NotificationDelivery.deliver_after <= utcnow(),
                )
                .order_by(NotificationDelivery.created_at.asc())
                .limit(limit)
                .all()
            )
            if not rows:
                return []

            now = utcnow()
            items: list[dict[str, Any]] = []
            for row in rows:
                self._mark_delivery_sent_row(row, now=now)
                items.append(self._serialize_delivery_item(row))
            db.commit()
            return items

    def mark_inapp_delivery_sent(self, user_id: str, delivery_id: str) -> bool:
        with SessionLocal() as db:
            row = (
                db.query(NotificationDelivery)
                .filter(
                    NotificationDelivery.id == delivery_id,
                    NotificationDelivery.user_id == user_id,
                    NotificationDelivery.channel == "inapp",
                    NotificationDelivery.status == "pending",
                    NotificationDelivery.deliver_after <= utcnow(),
                )
                .one_or_none()
            )
            if row is None:
                return False
            self._mark_delivery_sent_row(row, now=utcnow())
            db.commit()
            return True

    def _enqueue_deliveries(
        self,
        db: Session,
        *,
        outbox_id: str,
        payload: dict[str, Any],
        user_ids: set[str],
    ) -> list[NotificationDelivery]:
        if not user_ids:
            return []

        settings = get_settings()
        now = utcnow()
        inapp_deliver_after = now + timedelta(seconds=settings.notification_inapp_delay_seconds)
        bark_deliver_after = now + timedelta(seconds=settings.notification_batch_window_seconds)
        portal_users = (
            db.query(PortalUser)
            .filter(PortalUser.id.in_(list(user_ids)))
            .all()
        )
        user_map = {user.id: user for user in portal_users}
        inapp_deliveries: list[NotificationDelivery] = []

        for user_id in user_ids:
            inapp_delivery = self._ensure_delivery(
                db,
                outbox_id=outbox_id,
                user_id=user_id,
                channel="inapp",
                payload=payload,
                deliver_after=inapp_deliver_after,
            )
            if inapp_delivery is not None:
                inapp_deliveries.append(inapp_delivery)

            user = user_map.get(user_id)
            if not settings.enable_bark_notifications or user is None:
                continue
            bark_key = (user.notify_bark_key or "").strip()
            if not bark_key or not bool(user.notify_bark_enabled):
                continue
            self._ensure_delivery(
                db,
                outbox_id=outbox_id,
                user_id=user_id,
                channel="bark",
                payload=payload,
                deliver_after=bark_deliver_after,
            )
        return inapp_deliveries

    def _ensure_delivery(
        self,
        db: Session,
        *,
        outbox_id: str,
        user_id: str,
        channel: str,
        payload: dict[str, Any],
        deliver_after,
    ) -> NotificationDelivery | None:
        exists = (
            db.query(NotificationDelivery.id)
            .filter(
                NotificationDelivery.outbox_id == outbox_id,
                NotificationDelivery.user_id == user_id,
                NotificationDelivery.channel == channel,
            )
            .first()
        )
        if exists:
            return None
        delivery = NotificationDelivery(
            outbox_id=outbox_id,
            user_id=user_id,
            channel=channel,
            payload=payload,
            status="pending",
            deliver_after=deliver_after,
        )
        db.add(delivery)
        return delivery

    @staticmethod
    def _serialize_delivery_item(row: NotificationDelivery) -> dict[str, Any]:
        return {
            "id": row.id,
            "outbox_id": row.outbox_id,
            "created_at": row.created_at.isoformat(),
            "payload": row.payload or {},
        }

    @staticmethod
    def _mark_delivery_sent_row(row: NotificationDelivery, *, now) -> None:
        row.status = "sent"
        row.sent_at = now
        row.attempts = (row.attempts or 0) + 1

    @staticmethod
    def _push_live_inapp_items(items: list[tuple[str, dict[str, Any]]]) -> None:
        for user_id, item in items:
            sse_manager.push_to_user(user_id, item)

    def _lock_pending_rows(self, batch_size: int) -> list[str]:
        settings = get_settings()
        with SessionLocal() as db:
            self._requeue_stale_processing_rows(db)
            query = (
                db.query(NotificationOutbox)
                .filter(
                    NotificationOutbox.status == "pending",
                    NotificationOutbox.available_at <= utcnow(),
                )
                .order_by(NotificationOutbox.created_at.asc())
                .limit(batch_size)
            )
            dialect_name = (db.bind.dialect.name if db.bind else "").lower()
            if dialect_name != "sqlite":
                query = query.with_for_update(skip_locked=True)
            rows = query.all()
            if not rows:
                return []

            now = utcnow()
            for row in rows:
                row.status = "processing"
                row.attempts = (row.attempts or 0) + 1
                row.processing_started_at = now
                row.last_error = None
            db.commit()
            return [row.id for row in rows]

    def _lock_pending_delivery_rows(self, batch_size: int) -> list[str]:
        settings = get_settings()
        with SessionLocal() as db:
            self._requeue_stale_delivery_rows(db)
            query = (
                db.query(NotificationDelivery)
                .filter(
                    NotificationDelivery.channel != "inapp",
                    NotificationDelivery.status == "pending",
                    NotificationDelivery.deliver_after <= utcnow(),
                )
                .order_by(NotificationDelivery.created_at.asc())
                .limit(batch_size)
            )
            dialect_name = (db.bind.dialect.name if db.bind else "").lower()
            if dialect_name != "sqlite":
                query = query.with_for_update(skip_locked=True)
            rows = query.all()
            if not rows:
                return []

            now = utcnow()
            for row in rows:
                row.status = "processing"
                row.attempts = (row.attempts or 0) + 1
                row.processing_started_at = now
                row.last_error = None
            db.commit()
            return [row.id for row in rows]

    def _requeue_stale_processing_rows(self, db: Session) -> None:
        settings = get_settings()
        stale_cutoff = utcnow() - timedelta(seconds=settings.notification_processing_timeout_seconds)
        rows = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.status == "processing",
                NotificationOutbox.processing_started_at.is_not(None),
                NotificationOutbox.processing_started_at <= stale_cutoff,
            )
            .all()
        )
        if not rows:
            return
        for row in rows:
            row.status = "pending"
            row.processing_started_at = None
            row.available_at = utcnow()
            row.last_error = "requeued stale processing row"
        db.commit()

    def _requeue_stale_delivery_rows(self, db: Session) -> None:
        settings = get_settings()
        stale_cutoff = utcnow() - timedelta(seconds=settings.notification_processing_timeout_seconds)
        rows = (
            db.query(NotificationDelivery)
            .filter(
                NotificationDelivery.channel != "inapp",
                NotificationDelivery.status == "processing",
                NotificationDelivery.processing_started_at.is_not(None),
                NotificationDelivery.processing_started_at <= stale_cutoff,
            )
            .all()
        )
        if not rows:
            return
        for row in rows:
            row.status = "pending"
            row.processing_started_at = None
            row.deliver_after = utcnow()
            row.last_error = "requeued stale delivery row"
        db.commit()

    def _handle_outbox_error(self, outbox_id: str, error_message: str) -> None:
        settings = get_settings()
        with SessionLocal() as db:
            row = db.query(NotificationOutbox).filter(NotificationOutbox.id == outbox_id).one_or_none()
            if row is None:
                return

            row.last_error = error_message[:1000]
            row.processing_started_at = None
            if row.attempts >= settings.notification_max_attempts:
                row.status = "failed"
            else:
                row.status = "pending"
                row.available_at = utcnow() + timedelta(seconds=settings.notification_retry_delay_seconds)
            db.commit()

    def _handle_delivery_error(self, delivery_id: str, error_message: str) -> None:
        settings = get_settings()
        with SessionLocal() as db:
            row = db.query(NotificationDelivery).filter(NotificationDelivery.id == delivery_id).one_or_none()
            if row is None:
                return

            row.last_error = error_message[:1000]
            row.processing_started_at = None
            if row.attempts >= settings.notification_max_attempts:
                row.status = "failed"
            else:
                row.status = "pending"
                row.deliver_after = utcnow() + timedelta(seconds=settings.notification_retry_delay_seconds)
            db.commit()

    def _deliver_external_notification(self, delivery: NotificationDelivery) -> None:
        if delivery.channel == "bark":
            self._send_bark_delivery(delivery)
            return
        raise ValueError(f"unsupported delivery channel: {delivery.channel}")

    def _send_bark_delivery(self, delivery: NotificationDelivery) -> None:
        settings = get_settings()
        bark_key = ((delivery.user.notify_bark_key if delivery.user else None) or "").strip()
        if not bark_key:
            raise ValueError("bark key not configured")

        payload = dict(delivery.payload or {})
        title = str(payload.get("title") or "格物简录通知").strip() or "格物简录通知"
        body = (
            str(payload.get("summary") or "").strip()
            or str(payload.get("body") or "").strip()
            or "有新的关注内容，请进入系统查看。"
        )
        url = f"{settings.bark_server_url.rstrip('/')}/{quote(bark_key, safe='')}/{quote(title, safe='')}/{quote(body[:512], safe='')}"
        params = {}
        source_url = str(payload.get("source_url") or "").strip()
        if source_url:
            params["url"] = source_url
        if settings.bark_push_group.strip():
            params["group"] = settings.bark_push_group.strip()
        if settings.bark_push_sound.strip():
            params["sound"] = settings.bark_push_sound.strip()
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()

    def reset_for_tests(self) -> None:
        self._matcher.reset()
        sse_manager.reset()


notification_engine = NotificationEngine()
