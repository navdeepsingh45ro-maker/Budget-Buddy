import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from datetime import datetime
from services.summary_service import FinancialSummaryGenerator, local_today
from services.notification_service import NotificationService
from models.budget_model import Budget
from models.notification_preferences_model import NotificationPreferences

logger = logging.getLogger("trigger_service")

def evaluate_budget_triggers(user_id: int, push_origin: str = None):
    """
    Evaluates budget thresholds and generates notifications if necessary.
    Designed to run as a background task.

    push_origin applies only to the highest threshold created in this run:
    crossing 100% at once also backfills 80% and 50% in the drawer, but the
    user's phone buzzes once.
    """
    db: Session = SessionLocal()
    try:
        now = local_today()
        
        # EXTENSION POINT: Notification Preferences
        prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
        if prefs and not prefs.notify_budget:
            return

        # 1. Generate Summary (re-uses existing calculation logic)
        summary = FinancialSummaryGenerator.generate_summary(user_id, db, now.month, now.year)
        if not summary:
            return
            
        percentage = summary.get("percentage_spent", 0)
        
        # 2. Fetch the budget to get budget ID and exact amount
        budget = db.query(Budget).filter(
            Budget.user_id == user_id, 
            Budget.year == now.year, 
            Budget.month == now.month
        ).first()
        
        if not budget:
            return
            
        budget_id = budget.id
        push_next = push_origin  # only the first alert actually created gets pushed

        # 3. Determine thresholds (Highest threshold takes priority)
        # NotificationService.create_budget_notification automatically deduplicates based on threshold
        if percentage >= 100:
            title = "Over Budget Alert" if percentage > 100 else "Budget Alert: 100% Used"
            message = f"You have exceeded your monthly budget of ₹{budget.monthly_budget}. You've spent {percentage}%." if percentage > 100 else f"Careful! You have used 100% of your budget for this month."
            created = NotificationService.create_budget_notification(
                db=db, user_id=user_id, push_origin=push_next,
                title=title,
                message=message,
                budget_id=budget_id, month=now.month, year=now.year, threshold=100
            )
            if created:
                push_next = None
        
        # Always check lower milestones to backfill them if they haven't triggered, 
        # but deduplication will prevent them from firing twice.
        if percentage >= 80:
            created = NotificationService.create_budget_notification(
                db=db, user_id=user_id, push_origin=push_next,
                title="Budget Alert: 80% Used",
                message=f"Careful! You have used {percentage}% of your budget for this month.",
                budget_id=budget_id, month=now.month, year=now.year, threshold=80
            )
            if created:
                push_next = None
            
        if percentage >= 50:
            created = NotificationService.create_budget_notification(
                db=db, user_id=user_id, push_origin=push_next,
                title="Budget Milestone: 50% Used",
                message="You've reached the halfway point of your monthly budget.",
                budget_id=budget_id, month=now.month, year=now.year, threshold=50
            )
            if created:
                push_next = None
            
    except Exception as e:
        logger.error(f"Failed to evaluate budget triggers for user {user_id}: {e}")
    finally:
        db.close()


def trigger_monthly_report_notification(user_id: int, month: int, year: int):
    """
    Called by a scheduled cron job on the 1st of each month to notify users
    that their previous month's report is ready.
    """
    db: Session = SessionLocal()
    try:
        # EXTENSION POINT: Notification Preferences
        prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
        if prefs and not prefs.notify_monthly:
            return
        
        # Ensure duplicate protection per month/year
        meta = {"report_month": month, "report_year": year}
        
        if NotificationService.has_duplicate(db, user_id, "monthly", meta):
            return

        NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Monthly Report Ready",
            message="Your monthly financial report is now available.",
            category="monthly",
            source="scheduler",
            icon="assessment",
            action_type="monthly_report",
            action_payload={"month": month, "year": year},
            priority="info",
            metadata_json=meta
        )
    finally:
        db.close()
