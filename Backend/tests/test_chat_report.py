"""Ask Buddy chat and the monthly report, with Gemini replaced by stubs."""
import json
from datetime import date

from tests.test_insights import freeze_today, seed
from tests.test_smoke import client

import services.gemini_chat as gemini_chat
import services.monthly_report as monthly_report
from services.gemini_client import GeminiUnavailable


def test_chat_sends_real_numbers_and_no_notes(monkeypatch):
    freeze_today(monkeypatch, date(2026, 9, 15))
    _, headers = seed("chat@example.com", 10000, 9, 2026, [(450, "Food", date(2026, 9, 10))])
    prompts = []

    def fake(prompt, temperature=0):
        prompts.append(prompt)
        return {"reply": "You've spent ₹450 so far."}

    monkeypatch.setattr(gemini_chat, "generate_json", fake)
    r = client.post("/ai/chat", json={"message": "How am I doing?"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "You've spent ₹450 so far."

    data = json.loads(prompts[0].split("Data:\n", 1)[1].split("\n\nUser's question:")[0])
    assert data["monthly_budget"] == 10000 and data["total_spent"] == 450
    assert data["days_left_including_today"] == 16
    assert data["spending_by_category"] == {"Food": 450}
    assert "note" not in json.dumps(data["recent_expenses"])   # seed() wrote note="x"


def test_chat_errors(monkeypatch):
    _, headers = seed("chaterr@example.com", 0, 9, 2026, [])

    def down(prompt, temperature=0):
        raise GeminiUnavailable("busy")

    monkeypatch.setattr(gemini_chat, "generate_json", down)
    assert client.post("/ai/chat", json={"message": "hi"}, headers=headers).status_code == 503
    assert client.post("/ai/chat", json={"message": "x" * 501}, headers=headers).status_code == 422
    assert client.post("/ai/chat", json={"message": "hi"}).status_code == 401


def test_chat_daily_limit(monkeypatch):
    user_id, headers = seed("chatlimit@example.com", 0, 9, 2026, [])
    monkeypatch.setattr(gemini_chat, "generate_json", lambda p, temperature=0: {"reply": "ok"})
    monkeypatch.setattr(gemini_chat, "MAX_CHATS_PER_DAY", 2)
    codes = [client.post("/ai/chat", json={"message": "hi"}, headers=headers).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_report_facts_by_code_commentary_cached(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 2))
    _, headers = seed("report@example.com", 5000, 9, 2026, [
        (3000, "Rent", date(2026, 9, 1)),
        (1500, "Food", date(2026, 9, 12)),
        (1100, "Transport", date(2026, 9, 20)),
        (4000, "Rent", date(2026, 8, 1)),
    ])
    calls = []

    def fake(prompt, temperature=0):
        calls.append(prompt)
        return {"take": "Rent took most of the month.", "tips": ["Plan food shopping weekly.", "Bad tip with 20%"]}

    monkeypatch.setattr(monthly_report, "generate_json", fake)
    body = client.get("/ai/monthly-report?month=9&year=2026", headers=headers).json()
    assert body["ai"] is True
    assert body["facts"][0] == "Spent ₹5,600 of your ₹5,000 budget (112%), ₹600 over budget"
    assert "Top categories: Rent ₹3,000 (54%), Food ₹1,500 (27%), Transport ₹1,100 (20%)" in body["facts"]
    assert "₹1,600 more than August" in body["facts"]
    assert body["tips"] == ["Plan food shopping weekly."]           # tip with numbers dropped
    assert body["report"].startswith("September 2026 at a glance\n• Spent ₹5,600")
    assert "Buddy's take\nRent took most of the month." in body["report"]

    client.get("/ai/monthly-report?month=9&year=2026", headers=headers)
    assert len(calls) == 1                                           # cached: no second AI call


def test_report_works_when_ai_is_down(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 2))
    _, headers = seed("reportdown@example.com", 0, 9, 2026, [(900, "Food", date(2026, 9, 3))])

    def down(prompt, temperature=0):
        raise GeminiUnavailable("busy")

    monkeypatch.setattr(monthly_report, "generate_json", down)
    r = client.get("/ai/monthly-report?month=9&year=2026", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ai"] is False
    assert body["facts"][0] == "Spent ₹900 (no budget set)"
    assert "isn't available right now" in body["take"]


def test_report_empty_month_and_bad_params():
    _, headers = seed("reportempty@example.com", 0, 9, 2026, [])
    body = client.get("/ai/monthly-report?month=3&year=2026", headers=headers).json()
    assert "No expenses logged" in body["report"]
    assert client.get("/ai/monthly-report?month=13&year=2026", headers=headers).status_code == 422


# ── Report months, coach tips from last month's report, auto-generation ──

def test_report_months_default_to_last_month(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 20))
    _, headers = seed("months2@example.com", 0, 10, 2026, [
        (100, "Food", date(2026, 10, 2)), (200, "Food", date(2026, 9, 5)),
        (300, "Rent", date(2026, 9, 1)), (50, "Food", date(2026, 7, 9)),
    ])
    body = client.get("/ai/report-months", headers=headers).json()
    assert [m["label"] for m in body["months"]] == ["October 2026 (so far)", "September 2026", "July 2026"]
    assert body["months"][1]["expense_count"] == 2
    assert body["default"] == {"year": 2026, "month": 9}     # last month, all of October


def test_report_months_default_falls_back_when_last_month_empty(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 20))
    _, headers = seed("months3@example.com", 0, 10, 2026, [(50, "Food", date(2026, 7, 9))])
    assert client.get("/ai/report-months", headers=headers).json()["default"] == {"year": 2026, "month": 7}


def test_coach_tip_comes_from_last_months_report_without_new_ai_calls(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 2))
    _, headers = seed("coach@example.com", 5000, 10, 2026, [(1200, "Food", date(2026, 9, 3))])
    calls = []
    tips = ["Plan food shopping once a week.", "Cook at home on weekdays.", "Set a soft limit for Food."]

    def fake(prompt, temperature=0):
        calls.append(1)
        return {"take": "Food led September.", "tips": tips}

    monkeypatch.setattr(monthly_report, "generate_json", fake)
    client.get("/ai/monthly-report?month=9&year=2026", headers=headers)
    assert len(calls) == 1

    body = client.get("/ai/insight", headers=headers).json()
    assert body["ai_tip"] == tips[2 % 3]                    # rotates by day of month
    assert body["ai_tip_source"] == "September report"
    assert len(calls) == 1                                  # tip reused, no extra AI call


def test_missed_first_of_month_still_generates_report(monkeypatch):
    from datetime import datetime
    import services.reminder_engine as reminder_engine
    from services.summary_service import APP_TIMEZONE
    from models.ai_report_model import AIReport
    from database import SessionLocal

    freeze_today(monkeypatch, date(2026, 8, 4))
    user_id, _ = seed("missed@example.com", 0, 7, 2026, [(700, "Bills", date(2026, 7, 15))])
    monkeypatch.setattr(monthly_report, "generate_json",
                        lambda p, temperature=0: {"take": "Bills were the main cost.", "tips": ["Review bills."]})

    reminder_engine.run_reminders(datetime(2026, 8, 4, 10, tzinfo=APP_TIMEZONE))   # server was off on the 1st
    reminder_engine.run_reminders(datetime(2026, 8, 5, 10, tzinfo=APP_TIMEZONE))
    db = SessionLocal()
    cached = db.query(AIReport).filter(AIReport.user_id == user_id, AIReport.month == 7).all()
    from models.notification_model import Notification
    ready = db.query(Notification).filter(Notification.user_id == user_id, Notification.category == "monthly").all()
    db.close()
    assert len(cached) == 1 and cached[0].content["tips"] == ["Review bills."]
    assert len(ready) == 1 and ready[0].title == "Your July report is ready"


def test_concurrent_report_requests_dont_crash_or_double_call(monkeypatch):
    """Regression: dashboard pre-generation and a report click at the same moment used to crash (500)."""
    import threading
    import time
    from database import SessionLocal

    freeze_today(monkeypatch, date(2026, 10, 2))
    user_id, _ = seed("race@example.com", 1000, 9, 2026, [(500, "Food", date(2026, 9, 3))])
    calls = []

    def slow(prompt, temperature=0):
        calls.append(1)
        time.sleep(0.3)
        return {"take": "Food was the main cost.", "tips": ["Plan meals."]}

    monkeypatch.setattr(monthly_report, "generate_json", slow)
    errors = []

    def run():
        db = SessionLocal()
        try:
            monthly_report.build_monthly_report(db, user_id, 9, 2026)
        except Exception as e:
            errors.append(e)
        finally:
            db.close()

    threads = [threading.Thread(target=run) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []
    assert len(calls) == 1


def test_chat_can_answer_about_last_month(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 2))
    _, headers = seed("chatlast@example.com", 0, 10, 2026, [(1200, "Transport", date(2026, 9, 28))])
    prompts = []
    monkeypatch.setattr(gemini_chat, "generate_json", lambda p, temperature=0: prompts.append(p) or {"reply": "ok"})
    client.post("/ai/chat", json={"message": "Where did my money go in September?"}, headers=headers)
    assert '"September_spending_by_category": {\n  "Transport": 1200.0' in prompts[0]
