"""Summary numbers, rule-based Coach Insight, and how rarely the AI tip is requested."""
from datetime import date

import pytest

from tests.test_smoke import client, register_and_login

import services.ai_insight_generator as ai_insight_generator
import services.insight_updater as insight_updater
import services.monthly_report as monthly_report
import services.summary_service as summary_service
from database import SessionLocal
from models.budget_model import Budget
from models.expense_model import Expense
from models.user_model import User
from services.insight_engine import build_insight
from services.summary_service import FinancialSummaryGenerator


def freeze_today(monkeypatch, day: date):
    monkeypatch.setattr(summary_service, "local_today", lambda: day)
    monkeypatch.setattr(insight_updater, "local_today", lambda: day)
    monkeypatch.setattr(monthly_report, "local_today", lambda: day)


def seed(email, budget, month, year, expenses):
    """Create a user with a budget and (amount, category, date) expenses directly in the DB."""
    headers = register_and_login(email)
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if budget:
        db.add(Budget(user_id=user.id, monthly_budget=budget, month=month, year=year))
    for amount, category, day in expenses:
        db.add(Expense(user_id=user.id, amount=amount, category=category, expense_date=day, note="x"))
    db.commit()
    user_id = user.id
    db.close()
    return user_id, headers


def summary_for(user_id):
    db = SessionLocal()
    try:
        return FinancialSummaryGenerator.generate_summary(user_id, db)
    finally:
        db.close()


# ── Summary numbers ─────────────────────────────────────────────

def test_screenshot_case_last_day_of_month(monkeypatch):
    """30 Sep, ₹11,000 budget, ₹20 spent: previously showed '0 days left' and '₹0/day'."""
    freeze_today(monkeypatch, date(2026, 9, 30))
    user_id, headers = seed("lastday@example.com", 11000, 9, 2026, [(20, "Food", date(2026, 9, 30))])

    s = summary_for(user_id)
    assert s["days_left"] == 1                      # today still counts
    assert s["safe_daily_limit"] == 10980
    assert s["remaining_budget"] == 10980

    insight = build_insight(s)
    assert insight["situation"] == "last_day"
    assert "under 1%" in insight["insight"]
    assert "₹10,980" in insight["reminder"]

    body = client.get("/ai/insight", headers=headers).json()
    assert body["insight"] == insight["insight"]
    assert "₹0/day" not in body["reminder"]
    assert client.get("/analytics", headers=headers).json()["days_left"] == 1


def test_first_day_counts_whole_month(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 1))
    user_id, _ = seed("firstday@example.com", 3000, 9, 2026, [])
    s = summary_for(user_id)
    assert s["days_left"] == 30 and s["elapsed_days"] == 1
    assert s["safe_daily_limit"] == 100


def test_only_this_months_expenses_are_counted(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 15))
    user_id, _ = seed("months@example.com", 10000, 9, 2026, [
        (500, "Food", date(2026, 9, 2)),
        (700, "Food", date(2026, 8, 10)),   # last month, same period
        (900, "Rent", date(2026, 10, 1)),   # next month
    ])
    s = summary_for(user_id)
    assert s["total_spent"] == 500
    assert s["last_month_same_period"] == 700
    assert s["last_month_name"] == "August"


def test_pace_and_projection(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 10))
    user_id, _ = seed("pace@example.com", 30000, 9, 2026, [(20000, "Shopping", date(2026, 9, 5))])
    s = summary_for(user_id)
    assert s["average_daily_spending"] == 2000
    assert s["projected_month_total"] == 60000
    assert s["expected_spend_to_date"] == 10000
    assert s["days_left"] == 21
    assert build_insight(s)["situation"] == "projected_overspend"


# ── Rule priority ───────────────────────────────────────────────

BASE = dict(
    current_month="September", year=2026, month=9, monthly_budget=10000, total_spent=3000,
    remaining_budget=7000, percentage_spent=30.0, days_left=16, elapsed_days=15, days_in_month=30,
    safe_daily_limit=437.5, expense_count=5, average_daily_spending=200, projected_month_total=6000,
    top_category="Food", top_category_amount=1000, top_category_share=33.3, last_7_days=1400,
    previous_7_days=1400, last_month_same_period=0, last_month_name="August",
)


def situation(**overrides):
    return build_insight({**BASE, **overrides})["situation"]


def test_rule_priority():
    assert situation(monthly_budget=0) == "no_budget"
    assert situation(expense_count=0) == "no_expenses"
    assert situation(total_spent=12000, remaining_budget=-2000) == "over_budget"
    assert situation(days_left=1) == "last_day"
    assert situation(projected_month_total=15000) == "projected_overspend"
    assert situation(last_7_days=2500, previous_7_days=1000) == "weekly_spike"
    assert situation(top_category_share=70, top_category_amount=2100) == "category_heavy:Food"
    assert situation(last_month_same_period=5000) == "better_than_last_month"
    assert situation(percentage_spent=20) == "under_pace"
    assert situation(percentage_spent=45) == "on_pace"


def test_over_budget_beats_everything():
    s = {**BASE, "total_spent": 12000, "remaining_budget": -2000, "projected_month_total": 24000,
         "top_category_share": 90, "days_left": 1}
    insight = build_insight(s)
    assert insight["situation"] == "over_budget"
    assert "₹2,000 over" in insight["insight"]
    assert "October starts tomorrow" in insight["reminder"]


# ── AI usage ────────────────────────────────────────────────────

def test_ai_tip_only_requested_when_situation_changes(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 10))
    calls = []
    monkeypatch.setattr(insight_updater, "generate_coach_tip",
                        lambda insight, summary: calls.append(insight["situation"]) or "Nice work.")
    user_id, headers = seed("aicalls@example.com", 30000, 9, 2026, [(100, "Food", date(2026, 9, 2))])

    insight_updater.refresh_user_insight(user_id)
    assert len(calls) == 1

    # More spending in the same situation: no new AI call.
    db = SessionLocal()
    db.add(Expense(user_id=user_id, amount=50, category="Food", expense_date=date(2026, 9, 3)))
    db.commit(); db.close()
    insight_updater.refresh_user_insight(user_id)
    assert len(calls) == 1

    body = client.get("/ai/insight", headers=headers).json()
    assert body["ai_tip"] == "Nice work."

    # Big purchase changes the situation: one new call, and the old tip is hidden until then.
    db = SessionLocal()
    db.add(Expense(user_id=user_id, amount=25000, category="Shopping", expense_date=date(2026, 9, 9)))
    db.commit(); db.close()
    stale = client.get("/ai/insight", headers=headers).json()
    assert stale["situation"] == "projected_overspend"
    assert len(calls) == 2  # queued by the GET above


def test_ai_tip_daily_cap(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 10))
    calls = []
    monkeypatch.setattr(insight_updater, "generate_coach_tip",
                        lambda insight, summary: calls.append(1) or "Tip.")
    user_id, _ = seed("aicap@example.com", 1000, 9, 2026, [])

    budgets = [1000, 0, 1000, 0, 1000]  # flip between no_budget and no_expenses situations
    db = SessionLocal()
    for value in budgets:
        db.query(Budget).filter(Budget.user_id == user_id).update({"monthly_budget": value})
        db.commit()
        insight_updater.refresh_user_insight(user_id)
    db.close()
    assert len(calls) == insight_updater.MAX_TIPS_PER_DAY


@pytest.mark.parametrize("tip,accepted", [
    ("Planning meals ahead can make the rest of the month feel easy.", True),
    ("Try to keep it under ₹300 a day.", False),
    ("You've used 40% already.", False),
    ("", False),
])
def test_ai_tip_with_numbers_is_rejected(monkeypatch, tip, accepted):
    monkeypatch.setattr(ai_insight_generator, "generate_json", lambda prompt: {"tip": tip})
    result = ai_insight_generator.generate_coach_tip(
        {"insight": "x", "situation": "on_pace", "severity": "info"}, {**BASE})
    assert (result == tip) if accepted else (result is None)
