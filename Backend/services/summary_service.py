import calendar
from datetime import datetime
from sqlalchemy.orm import Session
from models.expense_model import Expense
from models.budget_model import Budget


class FinancialSummaryGenerator:
    """
    Generates a compact, deterministic financial summary for any month.
    This summary is structured for consumption by AI services (insights, reports, forecasting)
    and dashboard analytics without exposing raw transaction text or personal identifiers.

    When month/year are omitted, defaults to the current month (preserving original behavior).
    When provided, generates a historical summary for that specific month.
    """

    @staticmethod
    def generate_summary(user_id: int, db: Session, month: int = None, year: int = None) -> dict:
        now = datetime.now()

        # Default to current month if not specified
        target_month = month if month is not None else now.month
        target_year = year if year is not None else now.year
        total_days_in_month = calendar.monthrange(target_year, target_month)[1]

        # Determine if this is the current month or a past month
        is_current_month = (target_month == now.month and target_year == now.year)
        elapsed_days = now.day if is_current_month else total_days_in_month
        days_left = max(0, total_days_in_month - now.day) if is_current_month else 0

        month_name = datetime(target_year, target_month, 1).strftime("%B")

        # Fetch user's expenses for the target month
        all_expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
        month_expenses = []
        for e in all_expenses:
            effective_date = e.expense_date if e.expense_date else e.created_at
            if effective_date and effective_date.month == target_month and effective_date.year == target_year:
                month_expenses.append(e)

        # Fetch user's budget for the target month
        budget_record = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.month == target_month,
            Budget.year == target_year
        ).first()

        monthly_budget = budget_record.monthly_budget if budget_record else 0.0
        total_spent = sum(e.amount for e in month_expenses)
        remaining_budget = monthly_budget - total_spent
        percentage_spent = round((total_spent / monthly_budget * 100), 2) if monthly_budget > 0 else 0.0

        # Category breakdown
        category_totals = {}
        for e in month_expenses:
            cat = str(e.category) if e.category else "Other"
            category_totals[cat] = category_totals.get(cat, 0.0) + e.amount

        if category_totals:
            top_category = max(category_totals, key=category_totals.get)
            top_category_amount = category_totals[top_category]
        else:
            top_category = None
            top_category_amount = 0.0

        expense_count = len(month_expenses)

        # Time-based calculations
        average_daily_spending = round(total_spent / elapsed_days, 2) if elapsed_days > 0 else 0.0

        return {
            "current_month": month_name,
            "monthly_budget": monthly_budget,
            "total_spent": total_spent,
            "remaining_budget": remaining_budget,
            "percentage_spent": percentage_spent,
            "top_category": top_category,
            "top_category_amount": top_category_amount,
            "expense_count": expense_count,
            "average_daily_spending": average_daily_spending,
            "days_left": days_left
        }

