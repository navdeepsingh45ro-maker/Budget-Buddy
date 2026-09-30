"""Reminder engine: time-based in-app notifications, run by the background scheduler.

Every reminder is plain code (no AI), respects the user's notification
preferences, and is de-duplicated with a date or period in its metadata, so the
scheduler can run as often as it likes without sending anything twice.

| Reminder        | When (app timezone)             | Preference        |
|-----------------|---------------------------------|-------------------|
| daily_log       | after 20:00, nothing logged today | notify_reminders  |
| bill_due        | from 09:00, the day before a recurring expense | notify_reminders |
| weekly_summary  | Mondays from 09:00, for last Mon-Sun | notify_weekly  |
| monthly_report  | the 1st from 09:00, for last month | notify_monthly    |
| budget_missing  | days 1-3 from 09:00, no budget set but one existed last month | notify_budget |
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from database import SessionLocal
from models.budget_model import Budget
from models.notification_preferences_model import NotificationPreferences
from models.recurring_transaction_model import RecurringTransaction
from models.user_model import User
from services.insight_engine import money, percent
from services.notification_service import NotificationService
from services.summary_service import APP_TIMEZONE, FinancialSummaryGenerator, fetch_expense_rows

logger = logging.getLogger("reminder_engine")

DAILY_LOG_HOUR = 20
MORNING_HOUR = 9


def run_reminders(now: datetime | None = None) -> dict:
    """Check every user once. Returns how many reminders of each type were created."""
    now = now or datetime.now(APP_TIMEZONE)
    db = SessionLocal()
    sent = {"daily_log": 0, "bill_due": 0, "weekly_summary": 0, "monthly_report": 0, "budget_missing": 0}
    try:
        prefs_by_user = {p.user_id: p for p in db.query(NotificationPreferences).all()}
        for (user_id,) in db.query(User.id).all():
            prefs = prefs_by_user.get(user_id)

            def enabled(field: str) -> bool:
                return prefs is None or bool(getattr(prefs, field, True))

            try:
                if enabled("notify_reminders") and now.hour >= DAILY_LOG_HOUR:
                    sent["daily_log"] += _daily_log(db, user_id, now.date())
                if enabled("notify_reminders") and now.hour >= MORNING_HOUR:
                    sent["bill_due"] += _bills_due(db, user_id, now.date())
                if enabled("notify_weekly") and now.weekday() == 0 and now.hour >= MORNING_HOUR:
                    sent["weekly_summary"] += _weekly_summary(db, user_id, now.date())
                if enabled("notify_monthly") and now.day == 1 and now.hour >= MORNING_HOUR:
                    sent["monthly_report"] += _monthly_report(db, user_id, now.date())
                if enabled("notify_budget") and now.day <= 3 and now.hour >= MORNING_HOUR:
                    sent["budget_missing"] += _budget_missing(db, user_id, now.date())
            except Exception:
                db.rollback()
                logger.exception("Reminders failed for user %s", user_id)
    finally:
        db.close()
    if any(sent.values()):
        logger.info("Reminders sent: %s", sent)
    return sent


def _already_sent(db: Session, user_id: int, category: str, meta: dict) -> bool:
    return NotificationService.has_duplicate(db, user_id, category, meta)


def _daily_log(db: Session, user_id: int, today: date) -> int:
    meta = {"reminder_type": "daily_log", "date": today.isoformat()}
    if _already_sent(db, user_id, "reminder", meta):
        return 0
    if fetch_expense_rows(db, user_id, today, today):
        return 0
    NotificationService.create_notification(
        db=db, user_id=user_id,
        title="Anything to log today?",
        message="You haven't logged any expenses today. It takes seconds with voice or a receipt photo.",
        category="reminder", source="scheduler", icon="edit_note",
        action_type="add_expense", priority="info", metadata_json=meta,
        expires_at=datetime.utcnow() + timedelta(hours=16),
    )
    return 1


def _bills_due(db: Session, user_id: int, today: date) -> int:
    tomorrow = today + timedelta(days=1)
    bills = db.query(RecurringTransaction).filter(
        RecurringTransaction.user_id == user_id,
        RecurringTransaction.is_active == True,  # noqa: E712
        RecurringTransaction.next_run == tomorrow,
    ).all()
    count = 0
    for bill in bills:
        if bill.end_date and bill.end_date < tomorrow:
            continue
        meta = {"reminder_type": "bill_due", "recurring_id": bill.id, "date": tomorrow.isoformat()}
        if _already_sent(db, user_id, "reminder", meta):
            continue
        NotificationService.create_notification(
            db=db, user_id=user_id,
            title=f"{bill.title} is due tomorrow",
            message=f"{money(bill.amount)} for {bill.title} will be added to your expenses tomorrow.",
            category="reminder", source="scheduler", icon="event_upcoming",
            action_type="recurring", priority="info", metadata_json=meta,
            expires_at=datetime.utcnow() + timedelta(days=2),
        )
        count += 1
    return count


def _weekly_summary(db: Session, user_id: int, today: date) -> int:
    week_start = today - timedelta(days=7)          # last Monday
    week_end = today - timedelta(days=1)            # last Sunday
    meta = {"summary_type": "weekly", "week_start": week_start.isoformat()}
    if _already_sent(db, user_id, "weekly", meta):
        return 0

    rows = fetch_expense_rows(db, user_id, week_start - timedelta(days=7), week_end)
    this_week = [r for r in rows if r[2] >= week_start]
    if not this_week:
        return 0
    total = sum(r[0] for r in this_week)
    before = sum(r[0] for r in rows if r[2] < week_start)

    by_category: dict[str, float] = {}
    for amount, category, _ in this_week:
        by_category[category] = by_category.get(category, 0) + amount
    top = max(by_category, key=by_category.get)

    message = f"You spent {money(total)} across {len(this_week)} expense{'s' * (len(this_week) != 1)}. Top: {top} ({money(by_category[top])})."
    if before > 0:
        change = (total - before) / before * 100
        if abs(change) >= 5:
            direction = "more" if change > 0 else "less"
            message += f" That's {percent(abs(change))} {direction} than the week before."

    NotificationService.create_notification(
        db=db, user_id=user_id,
        title="Your week in review",
        message=message,
        category="weekly", source="scheduler", icon="date_range",
        action_type="history", priority="info", metadata_json=meta,
    )
    return 1


def _monthly_report(db: Session, user_id: int, today: date) -> int:
    last_month_day = today.replace(day=1) - timedelta(days=1)
    month, year = last_month_day.month, last_month_day.year
    meta = {"report_month": month, "report_year": year}
    if _already_sent(db, user_id, "monthly", meta):
        return 0

    s = FinancialSummaryGenerator.generate_summary(user_id, db, month=month, year=year)
    if s["expense_count"] == 0:
        return 0
    if s["monthly_budget"] > 0:
        verdict = ("within budget" if s["remaining_budget"] >= 0
                   else f"{money(-s['remaining_budget'])} over budget")
        message = (f"You spent {money(s['total_spent'])} of your {money(s['monthly_budget'])} budget "
                   f"({percent(s['percentage_spent'])}), {verdict}.")
    else:
        message = f"You spent {money(s['total_spent'])} across {s['expense_count']} expenses."
    message += f" Top category: {s['top_category']}."

    NotificationService.create_notification(
        db=db, user_id=user_id,
        title=f"Your {s['current_month']} report is ready",
        message=message,
        category="monthly", source="scheduler", icon="assessment",
        action_type="monthly_report", action_payload={"month": month, "year": year},
        priority="info", metadata_json=meta,
    )
    return 1


def _budget_missing(db: Session, user_id: int, today: date) -> int:
    meta = {"reminder_type": "budget_missing", "month": today.month, "year": today.year}
    if _already_sent(db, user_id, "reminder", meta):
        return 0
    has_budget = db.query(Budget).filter(
        Budget.user_id == user_id, Budget.month == today.month, Budget.year == today.year
    ).first()
    if has_budget:
        return 0
    last_month_day = today.replace(day=1) - timedelta(days=1)
    previous = db.query(Budget).filter(
        Budget.user_id == user_id, Budget.month == last_month_day.month, Budget.year == last_month_day.year
    ).first()
    if not previous:
        return 0

    month_name = today.strftime("%B")
    NotificationService.create_notification(
        db=db, user_id=user_id,
        title=f"Set your {month_name} budget",
        message=f"Your budget last month was {money(previous.monthly_budget)}. Set one for {month_name} to keep tracking your pace.",
        category="reminder", source="scheduler", icon="account_balance_wallet",
        action_type="set_budget", priority="warning", metadata_json=meta,
    )
    return 1
