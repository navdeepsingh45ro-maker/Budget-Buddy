from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from schemas.budget_schema import BudgetDetailResponse, BudgetCreate
from models.budget_model import Budget
from models.expense_model import Expense
from models.user_model import User
from auth.auth2 import get_current_user 
from database import get_db
from datetime import datetime
from services.insight_updater import refresh_user_insight
from services.summary_service import FinancialSummaryGenerator

router = APIRouter()
@router.post("/budget/")
def create_budget(budget: BudgetCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.now()
    current_month = today.month
    current_year = today.year
    existing_budget = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.month == current_month,
        Budget.year == current_year
    ).first()

    if existing_budget:
        raise HTTPException(
            status_code=400,
            detail="Budget for this month already exists"
        )

    new_budget = Budget(
        monthly_budget=budget.monthly_budget,
        month=current_month,
        year=current_year,
        user_id=current_user.id
    )

    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    background_tasks.add_task(refresh_user_insight, current_user.id)

    return new_budget


@router.put("/budget/")
def update_budget(budget: BudgetCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_month = datetime.now().month
    current_year = datetime.now().year
    existing_budget = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.month == current_month, Budget.year == current_year).first()
    if existing_budget:
        existing_budget.monthly_budget = budget.monthly_budget
        db.commit()
        db.refresh(existing_budget)
        background_tasks.add_task(refresh_user_insight, current_user.id)
        return existing_budget
    else:
        raise HTTPException(status_code=404, detail="Budget for this month not found")

@router.get("/budget/", response_model=BudgetDetailResponse)
def get_budget(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_month = datetime.now().month
    current_year = datetime.now().year
    budget = db.query(Budget).filter(Budget.user_id == current_user.id, Budget.month == current_month, Budget.year == current_year).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget for this month not found")
    return budget


# ── Helper: Build rich status object ──────────────────────────
def _build_status(percentage_spent: float) -> dict:
    if percentage_spent > 100:
        return {"type": "over_budget", "label": "Over Budget", "color": "red"}
    elif percentage_spent >= 80:
        return {"type": "caution", "label": "Caution", "color": "orange"}
    elif percentage_spent >= 50:
        return {"type": "on_track", "label": "On Track", "color": "blue"}
    else:
        return {"type": "within_budget", "label": "Within Budget", "color": "green"}


# ── Budget History: List all months grouped by year ───────────
@router.get("/budget/history")
def get_budget_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.id
    ).order_by(Budget.year.desc(), Budget.month.desc()).all()

    if not budgets:
        return []

    # Pre-fetch all expenses once for efficiency
    all_expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()

    history = []
    for b in budgets:
        month_name = datetime(b.year, b.month, 1).strftime("%B")
        month_label = f"{month_name} {b.year}"

        # Calculate spending for this budget's month
        spent = 0.0
        for e in all_expenses:
            effective_date = e.expense_date if e.expense_date else e.created_at
            if effective_date and effective_date.month == b.month and effective_date.year == b.year:
                spent += e.amount

        remaining = b.monthly_budget - spent
        saved = max(0.0, remaining)
        percentage_spent = round((spent / b.monthly_budget * 100), 2) if b.monthly_budget > 0 else 0.0

        history.append({
            "month": b.month,
            "year": b.year,
            "month_label": month_label,
            "budget": b.monthly_budget,
            "spent": spent,
            "remaining": remaining,
            "saved": saved,
            "budget_progress": round(min(percentage_spent, 100), 2),
            "percentage_spent": percentage_spent,
            "status": _build_status(percentage_spent)
        })

    return history


# ── Budget History: Monthly Report Detail ─────────────────────
@router.get("/budget/history/{year}/{month}")
def get_monthly_report(year: int, month: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Validate month
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month. Must be 1-12.")

    budget_record = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.month == month,
        Budget.year == year
    ).first()

    if not budget_record:
        raise HTTPException(status_code=404, detail=f"No budget found for {month}/{year}")

    # Use the universal FinancialSummaryGenerator
    summary = FinancialSummaryGenerator.generate_summary(current_user.id, db, month=month, year=year)

    month_label = f"{summary['current_month']} {year}"
    remaining = summary["remaining_budget"]
    saved = max(0.0, remaining)
    percentage_spent = summary["percentage_spent"]

    # Find the largest expense for the month
    all_expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    month_expenses = []
    for e in all_expenses:
        effective_date = e.expense_date if e.expense_date else e.created_at
        if effective_date and effective_date.month == month and effective_date.year == year:
            month_expenses.append(e)

    largest_expense = None
    if month_expenses:
        biggest = max(month_expenses, key=lambda e: e.amount)
        expense_date = biggest.expense_date if biggest.expense_date else biggest.created_at
        largest_expense = {
            "amount": biggest.amount,
            "category": biggest.category,
            "date": str(expense_date.date()) if hasattr(expense_date, 'date') else str(expense_date)
        }

    # Category breakdown
    category_breakdown = {}
    for e in month_expenses:
        cat = str(e.category) if e.category else "Other"
        category_breakdown[cat] = category_breakdown.get(cat, 0.0) + e.amount

    return {
        "month_label": month_label,
        "monthly_budget": summary["monthly_budget"],
        "total_spent": summary["total_spent"],
        "remaining_budget": remaining,
        "saved": saved,
        "percentage_spent": percentage_spent,
        "budget_progress": round(min(percentage_spent, 100), 2),
        "expense_count": summary["expense_count"],
        "top_category": summary["top_category"],
        "top_category_amount": summary["top_category_amount"],
        "average_daily_spending": summary["average_daily_spending"],
        "category_breakdown": category_breakdown,
        "largest_expense": largest_expense,
        "status": _build_status(percentage_spent),
        "ai_report": {
            "status": "not_generated",
            "data": None
        }
    }

