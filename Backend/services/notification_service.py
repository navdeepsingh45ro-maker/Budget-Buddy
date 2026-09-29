import datetime
from sqlalchemy.orm import Session
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from models.notification_model import Notification
import json

class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        category: str,
        source: str = "system",
        icon: str = None,
        action_type: str = None,
        action_payload: dict = None,
        priority: str = "info",
        expires_at: datetime.datetime = None,
        metadata_json: dict = None
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            source=source,
            icon=icon,
            action_type=action_type,
            action_payload=action_payload,
            priority=priority,
            status="delivered",  # Using delivered immediately since push isn't implemented
            expires_at=expires_at,
            metadata_json=metadata_json
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def has_duplicate(
        db: Session,
        user_id: int,
        category: str,
        metadata_filters: dict
    ) -> bool:
        """
        Check if a notification with matching criteria already exists.
        For SQLite, filtering by JSON fields directly is tricky without JSON extensions.
        So we will fetch recent notifications of that category for the user and check locally.
        For a production PostgreSQL system, we'd query `metadata_json @> ...`.
        """
        recent = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.category == category
        ).order_by(Notification.created_at.desc()).limit(50).all()

        for notif in recent:
            if notif.metadata_json:
                # Check if all key/values in metadata_filters match notif.metadata_json
                match = True
                for k, v in metadata_filters.items():
                    if notif.metadata_json.get(k) != v:
                        match = False
                        break
                if match:
                    return True
        return False

    @staticmethod
    def create_budget_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        budget_id: int,
        month: int,
        year: int,
        threshold: int,
        icon: str = "warning"
    ):
        """
        Creates a budget notification only if one doesn't exist for this budget/month/threshold.
        """
        meta = {
            "budget_id": budget_id,
            "month": month,
            "year": year,
            "threshold": threshold
        }
        
        if NotificationService.has_duplicate(db, user_id, "budget", meta):
            return None # Duplicate prevented

        priority = "warning"
        if threshold >= 100:
            priority = "critical"
        elif threshold <= 50:
            priority = "info"

        return NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            category="budget",
            source="budget",
            icon=icon,
            action_type="budget_history",
            action_payload={"year": year, "month": month},
            priority=priority,
            metadata_json=meta
        )

    @staticmethod
    def create_ai_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        insight_type: str,
        month: int = None,
        year: int = None
    ):
        meta = {"insight_type": insight_type}
        if month and year:
            meta["month"] = month
            meta["year"] = year

        # Prevent duplicate monthly AI notifications
        if insight_type == "monthly_report" and NotificationService.has_duplicate(db, user_id, "ai", meta):
            return None

        return NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            category="ai",
            source="ai",
            icon="auto_awesome",
            action_type="ai_insight",
            action_payload={"insight_type": insight_type, "year": year, "month": month},
            priority="success",
            metadata_json=meta
        )

    @staticmethod
    def create_system_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        icon: str = "info"
    ):
        return NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            category="system",
            source="system",
            icon=icon,
            priority="info"
        )

    @staticmethod
    def create_reminder_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        reminder_type: str,
        expires_in_hours: int = 24
    ):
        meta = {"reminder_type": reminder_type}
        
        # Don't send multiple of the exact same reminder on the same day if they haven't expired
        if NotificationService.has_duplicate(db, user_id, "reminder", meta):
            # To be more exact, we might want to only deduplicate active ones, but for simplicity here:
            pass # Or implement date-based duplicate checking

        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=expires_in_hours)
        return NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title=title,
            message=message,
            category="reminder",
            source="scheduler",
            icon="notifications_active",
            priority="info",
            expires_at=expires_at,
            metadata_json=meta
        )

    # --- Query and Update Methods ---

    @staticmethod
    def get_notifications(db: Session, user_id: int, limit: int = 50, offset: int = 0):
        # Cleanup expired notifications first (soft or ignore them in query)
        now = datetime.datetime.utcnow()
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_archived == False,
            (Notification.expires_at == None) | (Notification.expires_at > now)
        ).order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        now = datetime.datetime.utcnow()
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_archived == False,
            Notification.is_read == False,
            (Notification.expires_at == None) | (Notification.expires_at > now)
        ).count()

    @staticmethod
    def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if notification:
            notification.is_read = True
            db.commit()
            return True
        return False

    @staticmethod
    def mark_all_read(db: Session, user_id: int):
        db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({"is_read": True})
        db.commit()

    @staticmethod
    def delete_notification(db: Session, user_id: int, notification_id: int) -> bool:
        notification = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        if notification:
            db.delete(notification)
            db.commit()
            return True
        return False
