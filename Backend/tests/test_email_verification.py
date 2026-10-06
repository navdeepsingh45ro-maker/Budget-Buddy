"""Sign-up email verification: no login until the emailed code is entered."""
from datetime import datetime, timedelta

from tests.test_smoke import client, verification_codes

import routes.auth_routes as auth_routes
import services.email_verification as email_verification
from database import SessionLocal
from models.email_verification_model import EmailVerification
from models.user_model import User



def signup(email, password="Longenough1"):
    return client.post("/users/", json={"name": "New", "email": email, "password": password,
                                        "age_group": "18_plus", "accept_terms": True})


def login(email, password="Longenough1"):
    return client.post("/login", json={"email": email, "password": password})


def test_cannot_log_in_until_email_is_verified():
    r = signup("Fresh@Example.com")
    assert r.status_code == 200 and r.json() == {"message": "User created successfully",
                                                 "verification_required": True, "email": "fresh@example.com"}
    first_code = verification_codes["fresh@example.com"]

    assert login("fresh@example.com", "wrong-password").status_code == 401     # wrong password reveals nothing
    r = login("fresh@example.com")
    assert r.status_code == 403 and "verify your email" in r.json()["detail"]
    new_code = verification_codes["fresh@example.com"]                          # login sent a fresh code

    wrong = "000000" if new_code != "000000" else "111111"
    assert client.post("/auth/verify-email", json={"email": "fresh@example.com", "code": wrong}).status_code == 400
    if first_code != new_code:                                                  # the earlier code was replaced
        assert client.post("/auth/verify-email", json={"email": "fresh@example.com", "code": first_code}).status_code == 400

    r = client.post("/auth/verify-email", json={"email": "FRESH@example.com", "code": new_code})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/users/me", headers=headers).json()["email"] == "fresh@example.com"
    assert login("fresh@example.com").status_code == 200
    # A used code can't be replayed.
    assert client.post("/auth/verify-email", json={"email": "fresh@example.com", "code": new_code}).status_code == 400


def test_code_locks_after_too_many_wrong_guesses():
    signup("guesser@example.com")
    code = verification_codes["guesser@example.com"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(email_verification.MAX_ATTEMPTS):
        client.post("/auth/verify-email", json={"email": "guesser@example.com", "code": wrong})
    assert client.post("/auth/verify-email", json={"email": "guesser@example.com", "code": code}).status_code == 400
    # A resent code works again.
    assert client.post("/auth/resend-verification", json={"email": "guesser@example.com"}).status_code == 200
    code = verification_codes["guesser@example.com"]
    assert client.post("/auth/verify-email", json={"email": "guesser@example.com", "code": code}).status_code == 200


def test_resend_never_reveals_accounts_and_is_capped():
    unknown = client.post("/auth/resend-verification", json={"email": "ghost@example.com"})
    signup("capped@example.com")
    known = client.post("/auth/resend-verification", json={"email": "capped@example.com"})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    assert "ghost@example.com" not in verification_codes

    seen = {verification_codes["capped@example.com"]}
    for _ in range(8):
        client.post("/auth/resend-verification", json={"email": "capped@example.com"})
        seen.add(verification_codes["capped@example.com"])
    # Sign-up + resends: at most SENDS_PER_USER emails an hour reach the inbox.
    assert len(seen) <= email_verification.SENDS_PER_USER.max_events


def test_unverified_signup_cannot_be_overwritten_but_owner_can_recover(monkeypatch):
    reset_codes = {}
    monkeypatch.setattr(auth_routes, "send_password_reset_code",
                        lambda to, name, code, minutes_valid: reset_codes.__setitem__(to, code))
    signup("victim@example.com", password="SquatterPass1")                      # someone else used the victim's email
    r = signup("victim@example.com", password="RealOwner123")
    assert r.status_code == 400 and "already exists" in r.json()["detail"]

    # The real owner proves ownership with a password reset, which also confirms the email.
    assert client.post("/auth/forgot-password", json={"email": "victim@example.com"}).status_code == 200
    r = client.post("/auth/reset-password", json={"email": "victim@example.com", "code": reset_codes["victim@example.com"],
                                                  "new_password": "RealOwner123"})
    assert r.status_code == 200
    assert login("victim@example.com", "RealOwner123").status_code == 200
    assert login("victim@example.com", "SquatterPass1").status_code == 401


def test_stale_unverified_accounts_are_removed_on_next_signup():
    signup("abandoned@example.com")
    db = SessionLocal()
    user_id = db.query(User).filter(User.email == "abandoned@example.com").one().id
    db.query(EmailVerification).filter(EmailVerification.user_id == user_id).update(
        {"created_at": datetime.utcnow() - timedelta(hours=email_verification.UNVERIFIED_TTL_HOURS + 1)})
    db.commit(); db.close()

    assert signup("abandoned@example.com", password="SecondTry123").status_code == 200   # address is free again
    db = SessionLocal()
    assert db.query(User).filter(User.email == "abandoned@example.com").count() == 1
    db.close()
    code = verification_codes["abandoned@example.com"]
    assert client.post("/auth/verify-email", json={"email": "abandoned@example.com", "code": code}).status_code == 200
    assert login("abandoned@example.com", "SecondTry123").status_code == 200           # the new sign-up, not the old one
    assert login("abandoned@example.com", "Longenough1").status_code == 401


def test_accounts_from_before_verification_still_log_in():
    signup("legacy@example.com")
    db = SessionLocal()
    user_id = db.query(User).filter(User.email == "legacy@example.com").one().id
    db.query(EmailVerification).filter(EmailVerification.user_id == user_id).delete()
    db.commit(); db.close()
    assert login("legacy@example.com").status_code == 200
