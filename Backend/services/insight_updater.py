"""Keeps each user's optional AI coach tip in step with their spending situation.

Called in the background after an expense or budget changes. The rule-based
insight itself is computed live on every request (see /ai/insight), so this only
decides whether the AI tip needs refreshing. It calls Gemini only when the
situation id changes (e.g. "under_pace" -> "projected_overspend"), not when an
amount changes, and at most MAX_TIPS_PER_DAY times per user per day.
"""
import hashlib
import logging

from sqlalchemy.orm import Session

from database import SessionLocal
from models.ai_insight_model import AIInsight
from models.notification_preferences_model import NotificationPreferences
from services.ai_insight_generator import generate_coach_tip
from services.insight_engine import build_insight
from services.notification_service import NotificationService
from services.summary_service import FinancialSummaryGenerator, local_today

logger = logging.getLogger("insight_updater")

MAX_TIPS_PER_DAY = 3

# Situations worth a one-off in-app alert (once per month each).
ALERT_SITUATIONS = {
    "projected_overspend": "You're on course to overspend",
    "weekly_spike": "Spending jumped this week",
}


def situation_key(summary: dict, insight: dict) -> str:
    return f"{summary['year']}-{summary['month']:02d}:{insight['situation']}"


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def refresh_user_insight(user_id: int):
    db: Session = SessionLocal()
    try:
        summary = FinancialSummaryGenerator.generate_summary(user_id, db)
        insight = build_insight(summary)
        key = situation_key(summary, insight)

        record = db.query(AIInsight).filter(AIInsight.user_id == user_id).first()
        if record and record.summary_hash == key_hash(key):
            logger.info("User %s: situation unchanged (%s); no AI call.", user_id, key)
            return

        _maybe_alert(db, user_id, summary, insight)

        today = local_today().isoformat()
        meta = (record.summary_snapshot or {}) if record else {}
        tips_today = meta.get("tips_today", 0) if meta.get("tip_date") == today else 0
        if tips_today >= MAX_TIPS_PER_DAY:
            logger.info("User %s: daily AI tip limit reached; keeping rule-based text only.", user_id)
            return

        tip = generate_coach_tip(insight, summary)

        # Storage: summary_hash = hash of the situation the tip was written for,
        # insight = the AI tip ("" if the AI was unavailable), reminder unused.
        snapshot = {"situation_key": key, "tip_date": today, "tips_today": tips_today + 1}
        if record:
            record.summary_hash = key_hash(key)
            record.summary_snapshot = snapshot
            record.insight = tip or ""
            record.reminder = ""
        else:
            db.add(AIInsight(user_id=user_id, summary_hash=key_hash(key), summary_snapshot=snapshot,
                             insight=tip or "", reminder=""))
        db.commit()
        logger.info("User %s: AI tip refreshed for %s.", user_id, key)
    except Exception:
        logger.exception("Failed to refresh insight for user %s", user_id)
    finally:
        db.close()


def _maybe_alert(db: Session, user_id: int, summary: dict, insight: dict):
    situation = insight["situation"]
    if situation not in ALERT_SITUATIONS:
        return
    prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
    if prefs and not prefs.notify_ai:
        return
    meta = {"insight_type": situation, "month": summary["month"], "year": summary["year"]}
    if NotificationService.has_duplicate(db, user_id, "ai", meta):
        return
    NotificationService.create_ai_notification(
        db=db, user_id=user_id, title=ALERT_SITUATIONS[situation], message=insight["insight"],
        insight_type=situation, month=summary["month"], year=summary["year"],
    )
    db.commit()
