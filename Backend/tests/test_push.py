"""Push notifications: device registration and the agreed push rules."""
from datetime import date, datetime, timedelta

import pytest
from pywebpush import WebPushException

from tests.test_insights import seed
from tests.test_smoke import client

import services.push_service as push_service
from database import SessionLocal
from models.budget_model import Budget
from models.notification_model import Notification
from models.push_subscription_model import PushSubscription
from models.recurring_transaction_model import RecurringTransaction
from services.reminder_engine import run_reminders
from services.summary_service import APP_TIMEZONE, local_today

# Captured at import, before conftest's per-test patch replaces it.
REAL_IS_QUIET_HOURS = push_service.is_quiet_hours


def subscribe(headers, endpoint):
    return client.post("/push/subscribe", headers=headers,
                       json={"endpoint": endpoint, "keys": {"p256dh": "key", "auth": "secret"}})


def drawer(user_id, title_part):
    db = SessionLocal()
    rows = [n.title for n in db.query(Notification).filter(Notification.user_id == user_id).all() if title_part in n.title]
    db.close()
    return rows


# ── Registration ────────────────────────────────────────────────

def test_public_key_and_subscription_lifecycle():
    assert client.get("/push/public-key").json() == {"public_key": "test-public-key"}
    user_id, headers = seed("pushreg@example.com", 0, 1, 2026, [])

    assert subscribe({}, "https://push.example/a").status_code == 401
    assert subscribe(headers, "http://insecure.example/a").status_code == 400
    assert subscribe(headers, "https://push.example/a").status_code == 200
    assert subscribe(headers, "https://push.example/a").status_code == 200   # same device again: no duplicate

    db = SessionLocal()
    assert db.query(PushSubscription).filter(PushSubscription.user_id == user_id).count() == 1
    db.close()

    client.post("/push/unsubscribe", headers=headers, json={"endpoint": "https://push.example/a"})
    db = SessionLocal()
    assert db.query(PushSubscription).filter(PushSubscription.user_id == user_id).count() == 0
    db.close()


def test_device_moves_to_whoever_logs_in(push_calls):
    first_id, first = seed("pushfirst@example.com", 0, 1, 2026, [])
    second_id, second = seed("pushsecond@example.com", 0, 1, 2026, [])
    subscribe(first, "https://push.example/shared-phone")
    subscribe(second, "https://push.example/shared-phone")
    db = SessionLocal()
    owner = db.query(PushSubscription).filter(PushSubscription.endpoint == "https://push.example/shared-phone").one()
    assert owner.user_id == second_id
    db.close()


def test_test_push(push_calls):
    _, headers = seed("pushtest@example.com", 0, 1, 2026, [])
    assert client.post("/push/test", headers=headers).status_code == 404       # no devices yet
    subscribe(headers, "https://push.example/test")
    r = client.post("/push/test", headers=headers)
    assert r.status_code == 200 and r.json()["devices"] == 1
    assert push_calls[-1]["title"] == "Budget Buddy notifications are on"


# ── Rules ───────────────────────────────────────────────────────

@pytest.mark.parametrize("hour,origin,expected", [
    (14, "app", True), (23, "app", False), (6, "app", False), (8, "app", True),
    (14, "user_setup", True), (23, "user_setup", True), (3, "user_setup", True),
    (14, None, False), (23, None, False),
])
def test_should_push_matrix(monkeypatch, hour, origin, expected):
    """The real quiet-hours rule (conftest patches it to 'daytime' for other tests)."""
    monkeypatch.setattr(push_service, "is_quiet_hours", REAL_IS_QUIET_HOURS)
    now = datetime(2026, 10, 1, hour, 0, tzinfo=APP_TIMEZONE)
    assert push_service.should_push(origin, now) is expected


def test_app_reminder_pushed_by_day_but_not_at_night(push_calls, monkeypatch):
    user_id, headers = seed("pushnight@example.com", 0, 1, 2026, [])
    subscribe(headers, "https://push.example/night")

    monkeypatch.setattr(push_service, "is_quiet_hours", lambda now=None: True)
    run_reminders(datetime(2026, 7, 14, 23, 0, tzinfo=APP_TIMEZONE))           # daily-log nudge at 11 PM
    assert drawer(user_id, "Anything to log today?")                          # still in the drawer
    assert not [c for c in push_calls if c["endpoint"].endswith("/night")]    # but no buzz


def test_user_setup_bill_reminder_pushed_even_at_night(push_calls, monkeypatch):
    user_id, headers = seed("pushbill@example.com", 0, 1, 2026, [])
    subscribe(headers, "https://push.example/bill")
    db = SessionLocal()
    db.add(RecurringTransaction(user_id=user_id, title="Rent", amount=12000, category="Rent", frequency="monthly",
                                start_date=date(2026, 6, 15), next_run=date(2026, 7, 15), is_active=True))
    db.commit(); db.close()

    monkeypatch.setattr(push_service, "is_quiet_hours", lambda now=None: True)
    run_reminders(datetime(2026, 7, 14, 23, 0, tzinfo=APP_TIMEZONE))
    sent = [c for c in push_calls if c["endpoint"].endswith("/bill")]
    assert [c["title"] for c in sent] == ["Rent is due tomorrow"]
    assert sent[0]["action_type"] == "recurring" and sent[0]["tag"].startswith("bb-")


def test_budget_alert_from_manual_expense_is_not_pushed(push_calls):
    today = local_today()
    user_id, headers = seed("pushmanual@example.com", 1000, today.month, today.year, [])
    subscribe(headers, "https://push.example/manual")
    r = client.post("/expense/", headers=headers, json={"amount": 900, "category": "Food", "expense_date": today.isoformat()})
    assert r.status_code == 200
    assert drawer(user_id, "80% Used")                                         # alert is in the drawer
    assert not [c for c in push_calls if c["endpoint"].endswith("/manual")]   # no buzz: user caused it


def test_recurring_bill_crossing_100_pushes_once(push_calls):
    from services.recurring_transaction_service import RecurringTransactionService
    today = local_today()
    user_id, headers = seed("pushrecurring@example.com", 1000, today.month, today.year, [])
    subscribe(headers, "https://push.example/recurring")
    db = SessionLocal()
    db.add(RecurringTransaction(user_id=user_id, title="Gym", amount=1200, category="Health", frequency="monthly",
                                start_date=today - timedelta(days=30), next_run=today, is_active=True))
    db.commit()
    RecurringTransactionService.process_due_transactions(db)
    db.close()

    titles = [c["title"] for c in push_calls if c["endpoint"].endswith("/recurring")]
    assert "Recurring Expense Added" in titles
    budget_pushes = [t for t in titles if t.startswith(("Budget", "Over Budget"))]
    assert len(budget_pushes) == 1 and "Over Budget" in budget_pushes[0]      # one buzz, not 100+80+50
    assert len([t for t in drawer(user_id, "Budget") if not t.startswith("Welcome")]) == 3                                # all three still in the drawer


def test_expired_device_is_removed(push_calls, monkeypatch):
    user_id, headers = seed("pushgone@example.com", 0, 1, 2026, [])
    subscribe(headers, "https://push.example/gone")

    class Gone:
        status_code = 410

    def gone(subscription_info, data, **kwargs):
        raise WebPushException("gone", response=Gone())

    monkeypatch.setattr(push_service, "webpush", gone)
    assert client.post("/push/test", headers=headers).status_code == 404
    db = SessionLocal()
    assert db.query(PushSubscription).filter(PushSubscription.user_id == user_id).count() == 0
    db.close()
