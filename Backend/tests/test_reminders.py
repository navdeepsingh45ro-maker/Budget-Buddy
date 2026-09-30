"""Reminder engine: right reminder at the right time, once, and only if the user wants it."""
from datetime import date, datetime

from tests.test_smoke import register_and_login

from database import SessionLocal
from models.budget_model import Budget
from models.expense_model import Expense
from models.notification_model import Notification
from models.notification_preferences_model import NotificationPreferences
from models.recurring_transaction_model import RecurringTransaction
from models.user_model import User
from services.reminder_engine import run_reminders
from services.summary_service import APP_TIMEZONE


def at(y, m, d, hour):
    return datetime(y, m, d, hour, 0, tzinfo=APP_TIMEZONE)


def new_user(email):
    register_and_login(email)
    db = SessionLocal()
    user_id = db.query(User).filter(User.email == email).first().id
    db.close()
    return user_id


def add(*objects):
    db = SessionLocal()
    db.add_all(objects)
    db.commit()
    db.close()


def notes(user_id, category=None):
    db = SessionLocal()
    q = db.query(Notification).filter(Notification.user_id == user_id, Notification.source == "scheduler")
    if category:
        q = q.filter(Notification.category == category)
    rows = [(n.category, n.title, n.message, n.action_type) for n in q.all()]
    db.close()
    return rows


def set_pref(user_id, **values):
    db = SessionLocal()
    db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).update(values)
    db.commit()
    db.close()


def test_daily_log_only_in_evening_only_if_nothing_logged_and_only_once():
    lazy = new_user("lazy@example.com")
    busy = new_user("busy@example.com")
    add(Expense(user_id=busy, amount=50, category="Food", expense_date=date(2026, 7, 14)))

    run_reminders(at(2026, 7, 14, 15))
    assert notes(lazy, "reminder") == []                       # too early

    run_reminders(at(2026, 7, 14, 20))
    run_reminders(at(2026, 7, 14, 21))                         # scheduler runs again
    reminders = [n for n in notes(lazy, "reminder") if n[1] == "Anything to log today?"]
    assert len(reminders) == 1
    assert reminders[0][3] == "add_expense"
    assert not [n for n in notes(busy, "reminder") if n[1] == "Anything to log today?"]

    run_reminders(at(2026, 7, 15, 20))                         # a new day: a new reminder
    assert len([n for n in notes(lazy, "reminder") if n[1] == "Anything to log today?"]) == 2


def test_preferences_are_respected():
    quiet = new_user("quiet@example.com")
    set_pref(quiet, notify_reminders=False, notify_weekly=False)
    add(Expense(user_id=quiet, amount=100, category="Food", expense_date=date(2026, 7, 8)))
    run_reminders(at(2026, 7, 13, 21))                         # Monday evening
    assert notes(quiet) == []


def test_bill_due_the_day_before():
    user = new_user("bills@example.com")
    add(RecurringTransaction(user_id=user, title="Netflix", amount=199, category="Subscriptions",
                             frequency="monthly", start_date=date(2026, 6, 20), next_run=date(2026, 7, 21),
                             is_active=True),
        RecurringTransaction(user_id=user, title="Old gym", amount=999, category="Health",
                             frequency="monthly", start_date=date(2026, 1, 21), next_run=date(2026, 7, 21),
                             is_active=False))
    run_reminders(at(2026, 7, 19, 10))
    assert [n for n in notes(user, "reminder") if "due tomorrow" in n[1]] == []

    run_reminders(at(2026, 7, 20, 10))
    run_reminders(at(2026, 7, 20, 11))
    due = [n for n in notes(user, "reminder") if "due tomorrow" in n[1]]
    assert len(due) == 1
    assert due[0][1] == "Netflix is due tomorrow" and "₹199" in due[0][2]


def test_weekly_summary_on_monday_with_comparison():
    user = new_user("weekly@example.com")
    add(Expense(user_id=user, amount=300, category="Food", expense_date=date(2026, 7, 7)),       # week before
        Expense(user_id=user, amount=400, category="Food", expense_date=date(2026, 7, 14)),      # last week
        Expense(user_id=user, amount=200, category="Transport", expense_date=date(2026, 7, 16)))
    run_reminders(at(2026, 7, 19, 10))                         # Sunday: nothing
    assert notes(user, "weekly") == []

    run_reminders(at(2026, 7, 20, 10))                         # Monday
    run_reminders(at(2026, 7, 20, 12))
    weekly = notes(user, "weekly")
    assert len(weekly) == 1
    assert weekly[0][2] == ("You spent ₹600 across 2 expenses. Top: Food (₹400). "
                            "That's 100% more than the week before.")


def test_monthly_report_on_the_first():
    user = new_user("monthly@example.com")
    add(Budget(user_id=user, monthly_budget=5000, month=6, year=2026),
        Expense(user_id=user, amount=5600, category="Rent", expense_date=date(2026, 6, 5)))
    run_reminders(at(2026, 7, 1, 10))
    run_reminders(at(2026, 7, 1, 11))
    monthly = notes(user, "monthly")
    assert len(monthly) == 1
    assert monthly[0][1] == "Your June report is ready"
    assert "₹600 over budget" in monthly[0][2]


def test_budget_missing_reminder_only_if_budget_used_before():
    returning = new_user("returning@example.com")
    brand_new = new_user("brandnew@example.com")
    add(Budget(user_id=returning, monthly_budget=11000, month=6, year=2026))
    run_reminders(at(2026, 7, 2, 10))
    missing = [n for n in notes(returning, "reminder") if n[3] == "set_budget"]
    assert len(missing) == 1 and "₹11,000" in missing[0][2]
    assert not [n for n in notes(brand_new, "reminder") if n[3] == "set_budget"]

    add(Budget(user_id=brand_new, monthly_budget=1000, month=7, year=2026))
    run_reminders(at(2026, 7, 3, 10))                          # already has July budget
    assert not [n for n in notes(brand_new, "reminder") if n[3] == "set_budget"]
