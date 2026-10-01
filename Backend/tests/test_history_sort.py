from datetime import date, datetime

from tests.test_insights import seed
from tests.test_smoke import client
from database import SessionLocal
from models.expense_model import Expense


def test_history_sorts_by_expense_date_then_entry_time():
    _, headers = seed("history-sort@example.com", 10000, 9, 2026, [
        (120, "Food", date(2026, 9, 12)),
        (300, "Food", date(2026, 10, 1)),
        (200, "Food", date(2026, 9, 20)),
    ])

    newest = client.get("/expenses/query?sort=newest", headers=headers)
    assert newest.status_code == 200, newest.text
    assert [item["expense_date"] for item in newest.json()["expenses"]] == [
        "2026-10-01", "2026-09-20", "2026-09-12",
    ]

    oldest = client.get("/expenses/query?sort=oldest", headers=headers)
    assert oldest.status_code == 200, oldest.text
    assert [item["expense_date"] for item in oldest.json()["expenses"]] == [
        "2026-09-12", "2026-09-20", "2026-10-01",
    ]


def test_history_uses_created_date_for_legacy_expense_without_expense_date():
    user_id, headers = seed("history-legacy-sort@example.com", 10000, 9, 2026, [
        (120, "Food", date(2026, 9, 20)),
    ])
    db = SessionLocal()
    try:
        db.add(Expense(
            user_id=user_id,
            amount=100,
            category="Food",
            expense_date=None,
            created_at=datetime(2026, 9, 12, 8, 0),
            note="legacy",
        ))
        db.commit()
    finally:
        db.close()

    response = client.get("/expenses/query?sort=newest", headers=headers)
    assert response.status_code == 200, response.text
    assert [item["note"] for item in response.json()["expenses"]] == ["x", "legacy"]
