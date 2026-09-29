import json
import hashlib
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from services.summary_service import FinancialSummaryGenerator
from services.ai_insight_generator import AIInsightGenerator
from models.ai_insight_model import AIInsight

logger = logging.getLogger("insight_updater")

def refresh_user_insight(user_id: int):
    """
    Background task to refresh the AI insight for a user.
    Uses SHA-256 hashing to prevent redundant calls to Gemini.
    """
    db: Session = SessionLocal()
    try:
        # Generate current financial summary
        summary = FinancialSummaryGenerator.generate_summary(user_id, db)
        
        # Create a stable string representation and hash it
        # Sort keys to ensure deterministic hashing
        summary_str = json.dumps(summary, sort_keys=True)
        summary_hash = hashlib.sha256(summary_str.encode('utf-8')).hexdigest()
        
        # Check existing insight
        existing_insight = db.query(AIInsight).filter(AIInsight.user_id == user_id).first()
        
        if existing_insight and existing_insight.summary_hash == summary_hash:
            logger.info(f"Skipping AI generation for user {user_id}; financial summary hash unchanged.")
            return

        logger.info(f"Generating new AI insight for user {user_id}...")
        ai_generator = AIInsightGenerator()
        ai_response = ai_generator.generate_insight(summary)
        
        insight_text = ai_response.get("insight", "")
        reminder_text = ai_response.get("reminder", "")
        
        if existing_insight:
            existing_insight.summary_hash = summary_hash
            existing_insight.summary_snapshot = summary
            existing_insight.insight = insight_text
            existing_insight.reminder = reminder_text
        else:
            new_insight = AIInsight(
                user_id=user_id,
                summary_hash=summary_hash,
                summary_snapshot=summary,
                insight=insight_text,
                reminder=reminder_text
            )
            db.add(new_insight)
            
        db.commit()
        
        # Trigger AI Notification
        from services.notification_service import NotificationService
        from models.notification_preferences_model import NotificationPreferences
        from datetime import datetime
        
        prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
        if prefs and not prefs.notify_ai:
            logger.info(f"Skipping AI notification for user {user_id} due to preferences.")
        else:
            now = datetime.now()
            NotificationService.create_ai_notification(
            db=db,
            user_id=user_id,
            title="New AI Insight Available",
            message="Buddy generated new financial insights for this month.",
            insight_type="monthly_insight",
            month=now.month,
            year=now.year
            )
            # Commit the notification
            db.commit()
        
        logger.info(f"Successfully updated AI insight for user {user_id}.")
        
    except Exception as e:
        logger.error(f"Failed to refresh AI insight for user {user_id}: {e}")
    finally:
        db.close()
