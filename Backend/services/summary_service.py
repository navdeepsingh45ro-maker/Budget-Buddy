import calendar
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.budget_model import Budget
from models.expense_model import Expense

# "Today" must be the user's today, not the server's: a server in UTC is 5.5 hours
# behind India, which puts early-morning expenses on the wrong day or month.
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))


def local_today() -> date:
    return datetime.now(APP_TIMEZONE).date()


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def fetch_expense_rows(db: Session, user_id: int, start: date, end: date) -> list[tuple[float, str, date]]:
    """(amount, category, effective date) for expenses dated start..end inclusive.

    The effective date is expense_date, or created_at for old rows without one.
    Filtering happens in SQL so only the needed rows are loaded.
    """
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())
    start_dt = datetime.combine(start, datetime.min.time())
    rows = db.query(Expense.amount, Expense.category, Expense.expense_date, Expense.created_at).filter(
        Expense.user_id == user_id,
        or_(
            and_(Expense.expense_date.isnot(None), Expense.expense_date >= start, Expense.expense_date <= end),
            and_(Expense.expense_date.is_(None), Expense.created_at >= start_dt, Expense.created_at < end_dt),
        ),
    ).all()
    return [
        (float(amount or 0), category or "Other", expense_date or created_at.date())
        for amount, category, expense_date, created_at in rows
    ]


class FinancialSummaryGenerator:
    """
    Deterministic numbers for one month: totals, pace, projections and trends.
    Everything the dashboard, insights and AI features show comes from here,
    so the numbers are always consistent and never invented by the AI.

    When month/year are omitted, defaults to the current month.
    """

    @staticmethod
    def generate_summary(user_id: int, db: Session, month: int = None, year: int = None) -> dict:
        today = local_today()
        target_month = month if month is not None else today.month
        target_year = year if year is not None else today.year

        days_in_month = calendar.monthrange(target_year, target_month)[1]
        month_start = _month_start(target_year, target_month)
        month_end = date(target_year, target_month, days_in_month)
        is_current_month = (target_month == today.month and target_year == today.year)

        # Days counted so far, and days still available to spend (today included).
        elapsed_days = today.day if is_current_month else days_in_month
        days_left = (days_in_month - today.day + 1) if is_current_month else 0
        period_end = today if is_current_month else month_end

        prev_year, prev_month = _previous_month(target_year, target_month)
        prev_start = _month_start(prev_year, prev_month)
        rows = fetch_expense_rows(db, user_id, prev_start, month_end)
        month_rows = [r for r in rows if r[2] >= month_start]
        prev_rows = [r for r in rows if r[2] < month_start]

        budget_record = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.month == target_month,
            Budget.year == target_year,
        ).first()
        monthly_budget = float(budget_record.monthly_budget) if budget_record else 0.0

        total_spent = round(sum(r[0] for r in month_rows), 2)
        remaining_budget = round(monthly_budget - total_spent, 2)
        percentage_spent = round(total_spent / monthly_budget * 100, 2) if monthly_budget > 0 else 0.0

        category_totals: dict[str, float] = {}
        for amount, category, _ in month_rows:
            category_totals[category] = round(category_totals.get(category, 0.0) + amount, 2)
        top_category = max(category_totals, key=category_totals.get) if category_totals else None
        top_category_amount = category_totals.get(top_category, 0.0) if top_category else 0.0
        top_category_share = round(top_category_amount / total_spent * 100, 1) if total_spent > 0 else 0.0

        average_daily_spending = round(total_spent / elapsed_days, 2) if elapsed_days > 0 else 0.0

        # Pace: where spending "should" be by now if the budget were spread evenly.
        expected_spend_to_date = round(monthly_budget * elapsed_days / days_in_month, 2)
        projected_month_total = round(total_spent / elapsed_days * days_in_month, 2) if is_current_month else total_spent
        safe_daily_limit = round(remaining_budget / days_left, 2) if days_left > 0 and remaining_budget > 0 else 0.0

        # Short-term trend: last 7 days vs the 7 before (ending today, or at month end for past months).
        def spent_between(start: date, end: date) -> float:
            return round(sum(r[0] for r in rows if start <= r[2] <= end), 2)

        last_7_days = spent_between(period_end - timedelta(days=6), period_end)
        previous_7_days = spent_between(period_end - timedelta(days=13), period_end - timedelta(days=7))
        spent_today = spent_between(today, today) if is_current_month else 0.0

        # Same point last month, e.g. 1-15 Aug when today is 15 Sep.
        prev_days = calendar.monthrange(prev_year, prev_month)[1]
        prev_cutoff = date(prev_year, prev_month, min(elapsed_days, prev_days))
        last_month_same_period = round(sum(r[0] for r in prev_rows if r[2] <= prev_cutoff), 2)
        last_month_total = round(sum(r[0] for r in prev_rows), 2)

        largest = max(month_rows, key=lambda r: r[0]) if month_rows else None

        return {
            # Original keys (used by budget history, triggers, chat)
            "current_month": month_start.strftime("%B"),
            "monthly_budget": monthly_budget,
            "total_spent": total_spent,
            "remaining_budget": remaining_budget,
            "percentage_spent": percentage_spent,
            "top_category": top_category,
            "top_category_amount": top_category_amount,
            "expense_count": len(month_rows),
            "average_daily_spending": average_daily_spending,
            "days_left": days_left,
            # Calendar
            "year": target_year,
            "month": target_month,
            "is_current_month": is_current_month,
            "days_in_month": days_in_month,
            "elapsed_days": elapsed_days,
            # Pace and projection
            "expected_spend_to_date": expected_spend_to_date,
            "projected_month_total": projected_month_total,
            "safe_daily_limit": safe_daily_limit,
            # Breakdown and trends
            "category_totals": category_totals,
            "top_category_share": top_category_share,
            "largest_expense_amount": largest[0] if largest else 0.0,
            "largest_expense_category": largest[1] if largest else None,
            "spent_today": spent_today,
            "last_7_days": last_7_days,
            "previous_7_days": previous_7_days,
            "last_month_name": prev_start.strftime("%B"),
            "last_month_same_period": last_month_same_period,
            "last_month_total": last_month_total,
        }
