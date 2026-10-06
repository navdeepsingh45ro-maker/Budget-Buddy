"""Account management, settings, carry-over and account deletion."""
from datetime import date

from tests.test_insights import freeze_today, seed
from tests.test_smoke import client, register_and_login

import services.budget_carryover as budget_carryover
from database import Base, SessionLocal
from models.budget_model import Budget
from models.notification_model import Notification
from models.user_model import User
from routes.user_routes import USER_OWNED_MODELS

ADULT = {"age_group": "18_plus", "accept_terms": True}


def test_signup_requires_8_char_password_and_a_name():
    r = client.post("/users/", json={"name": "Short", "email": "short@example.com", "password": "abc123", **ADULT})
    assert r.status_code == 400 and "8 characters" in r.json()["detail"]
    r = client.post("/users/", json={"name": "   ", "email": "noname@example.com", "password": "Longenough1", **ADULT})
    assert r.status_code == 400


def test_signup_age_gate_and_consent():
    from models.user_consent_model import UserConsent

    def signup(email, **consent):
        return client.post("/users/", json={"name": "Kid", "email": email, "password": "Longenough1", **consent})

    def stored(email):
        db = SessionLocal()
        try:
            return db.query(User).filter(User.email == email).first()
        finally:
            db.close()

    # Under 13: refused, and nothing from the attempt is stored.
    r = signup("child@example.com", age_group="under_13", accept_terms=True)
    assert r.status_code == 403 and "13 or older" in r.json()["detail"]
    assert stored("child@example.com") is None

    # Missing age group, missing terms, or a 13-17 without parent consent: refused.
    assert signup("noage@example.com", accept_terms=True).status_code == 400
    assert signup("noterms@example.com", age_group="18_plus").status_code == 400
    r = signup("teen@example.com", age_group="13_17", accept_terms=True)
    assert r.status_code == 400 and "parent or guardian" in r.json()["detail"]
    assert not any(stored(e) for e in ("noage@example.com", "noterms@example.com", "teen@example.com"))

    # 13-17 with parent consent, and adults: accepted, and the consent is recorded.
    assert signup("teen@example.com", age_group="13_17", accept_terms=True, guardian_consent=True).status_code == 200
    assert signup("adult@example.com", **ADULT).status_code == 200
    db = SessionLocal()
    try:
        teen = db.query(UserConsent).join(User, User.id == UserConsent.user_id).filter(User.email == "teen@example.com").one()
        adult = db.query(UserConsent).join(User, User.id == UserConsent.user_id).filter(User.email == "adult@example.com").one()
        assert teen.age_group == "13_17" and teen.guardian_consent_at and teen.terms_version
        assert adult.age_group == "18_plus" and adult.guardian_consent_at is None
    finally:
        db.close()


def test_new_user_sees_tutorial_once_existing_users_dont():
    headers = register_and_login("newbie@example.com")
    assert client.get("/users/me/settings", headers=headers).json() == {"carry_over_budget": True, "onboarding_completed": False}
    client.put("/users/me/settings", headers=headers, json={"onboarding_completed": True})
    assert client.get("/users/me/settings", headers=headers).json()["onboarding_completed"] is True

    # Accounts created before the tutorial existed have no settings row.
    _, old_headers = seed("oldtimer@example.com", 0, 1, 2026, [])
    db = SessionLocal()
    from models.user_settings_model import UserSettings
    uid = db.query(User).filter(User.email == "oldtimer@example.com").one().id
    db.query(UserSettings).filter(UserSettings.user_id == uid).delete(); db.commit(); db.close()
    assert client.get("/users/me/settings", headers=old_headers).json()["onboarding_completed"] is True


def test_edit_name_and_change_password():
    headers = register_and_login("acct@example.com", password="FirstPass1")
    r = client.put("/users/me", headers=headers, json={"name": "  Navdeep  "})
    assert r.status_code == 200 and r.json()["name"] == "Navdeep" and "password" not in r.json()
    assert client.put("/users/me", headers=headers, json={"name": " "}).status_code == 400

    bad = client.post("/users/me/password", headers=headers, json={"current_password": "wrong", "new_password": "SecondPass2"})
    assert bad.status_code == 400 and "incorrect" in bad.json()["detail"]
    assert client.post("/users/me/password", headers=headers, json={"current_password": "FirstPass1", "new_password": "short"}).status_code == 400
    assert client.post("/users/me/password", headers=headers, json={"current_password": "FirstPass1", "new_password": "SecondPass2"}).status_code == 200
    assert client.post("/login", json={"email": "acct@example.com", "password": "SecondPass2"}).status_code == 200
    assert client.post("/login", json={"email": "acct@example.com", "password": "FirstPass1"}).status_code == 401


def test_budget_carries_over_once_and_respects_setting(monkeypatch):
    freeze_today(monkeypatch, date(2026, 10, 1))
    monkeypatch.setattr(budget_carryover, "local_today", lambda: date(2026, 10, 1))
    user_id, headers = seed("carry@example.com", 11000, 9, 2026, [])

    assert client.get("/budget/", headers=headers).json()["monthly_budget"] == 11000   # carried on first load
    client.get("/budget/", headers=headers)
    db = SessionLocal()
    assert db.query(Budget).filter(Budget.user_id == user_id, Budget.month == 10).count() == 1
    assert db.query(Notification).filter(Notification.user_id == user_id, Notification.title == "Your October budget is ready").count() == 1
    db.close()

    off_id, off_headers = seed("nocarry@example.com", 9000, 9, 2026, [])
    client.put("/users/me/settings", headers=off_headers, json={"carry_over_budget": False})
    assert client.get("/budget/", headers=off_headers).status_code == 404            # no budget created


def test_delete_account_removes_everything():
    user_id, headers = seed("goodbye@example.com", 5000, 9, 2026, [(100, "Food", date(2026, 9, 2))])
    client.post("/push/subscribe", headers=headers, json={"endpoint": "https://push.example/bye", "keys": {"p256dh": "k", "auth": "a"}})
    other_id, _ = seed("staying@example.com", 5000, 9, 2026, [(200, "Food", date(2026, 9, 2))])

    assert client.post("/users/me/delete", headers=headers, json={"password": "wrong"}).status_code == 400
    assert client.post("/users/me/delete", headers=headers, json={"password": "Str0ng!pass"}).status_code == 200

    db = SessionLocal()
    assert db.query(User).filter(User.id == user_id).count() == 0
    for model in USER_OWNED_MODELS:
        assert db.query(model).filter(model.user_id == user_id).count() == 0, model.__tablename__
    assert db.query(User).filter(User.id == other_id).count() == 1                    # nobody else touched
    db.close()
    assert client.get("/users/me", headers=headers).status_code == 401              # old token is useless


def test_delete_covers_every_table_with_user_data():
    """Guard: a future table with a user_id column must be added to USER_OWNED_MODELS."""
    covered = {m.__tablename__ for m in USER_OWNED_MODELS}
    with_user_id = {name for name, table in Base.metadata.tables.items() if "user_id" in table.columns}
    assert with_user_id <= covered, f"Not deleted with the account: {with_user_id - covered}"
