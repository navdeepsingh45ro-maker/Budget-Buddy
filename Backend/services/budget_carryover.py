"""Carry last month's budget into the new month, so the dashboard is never empty on the 1st.

On by default (Settings → Budget). Runs from the scheduler and lazily when the
budget/dashboard is loaded, whichever happens first. Creates nothing if the user
already set a budget this month, turned carry-over off, or had no budget last month.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from models.budget_model import Budget
from models.user_settings_model import UserSettings
from services.insight_engine import money
from services.locks import keyed_lock
from services.notification_service import NotificationService
from services.push_service import APP
from services.summary_service import local_today

logger = logging.getLogger("budget_carryover")


def carry_over_enabled(db: Session, user_id: int) -> bool:
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    return settings is None or bool(settings.carry_over_budget)


def ensure_budget_carried_over(db: Session, user_id: int) -> Budget | None:
    """Create this month's budget from last month's if needed. Returns the new budget, or None."""
    # The budgets table has no unique (user, month, year) rule, so serialise per user.
    with keyed_lock(("carryover", user_id)):
        return _carry_over(db, user_id)


def _carry_over(db: Session, user_id: int) -> Budget | None:
    today = local_today()
    if db.query(Budget.id).filter(Budget.user_id == user_id, Budget.month == today.month,
                                  Budget.year == today.year).first():
        return None
    if not carry_over_enabled(db, user_id):
        return None

    last = today.replace(day=1) - timedelta(days=1)
    previous = db.query(Budget).filter(Budget.user_id == user_id, Budget.month == last.month,
                                       Budget.year == last.year).first()
    if not previous:
        return None

    budget = Budget(user_id=user_id, monthly_budget=previous.monthly_budget, month=today.month, year=today.year)
    db.add(budget)
    db.commit()
    db.refresh(budget)

    month_name = today.strftime("%B")
    NotificationService.create_notification(
        db=db, user_id=user_id,
        title=f"Your {month_name} budget is ready",
        message=f"We carried over last month's {money(previous.monthly_budget)}. You can change it anytime on the Budget page.",
        category="budget", source="scheduler", icon="account_balance_wallet",
        action_type="set_budget", priority="info", push_origin=APP,
        metadata_json={"carryover_month": today.month, "carryover_year": today.year},
    )
    logger.info("Carried over budget %s for user %s into %s %s", previous.monthly_budget, user_id, month_name, today.year)
    return budget
