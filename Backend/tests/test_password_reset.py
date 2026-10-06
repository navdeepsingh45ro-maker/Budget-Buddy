"""Forgot-password flow: code emailed, wrong codes rejected, new password works."""
from tests.test_smoke import client, register_and_login

import routes.auth_routes as auth_routes

sent = {}


def capture_email(to, name, code, minutes_valid):
    sent[to] = code


auth_routes.send_password_reset_code = capture_email


def test_unknown_email_gets_same_response_and_no_email():
    r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "nobody@example.com" not in sent


def test_full_reset_flow():
    register_and_login("reset@example.com", password="OldPass!123")

    r = client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    code = sent["reset@example.com"]
    assert len(code) == 6 and code.isdigit()

    wrong = "000000" if code != "000000" else "111111"
    r = client.post("/auth/reset-password", json={"email": "reset@example.com", "code": wrong, "new_password": "NewPass!123"})
    assert r.status_code == 400

    r = client.post("/auth/reset-password", json={"email": "reset@example.com", "code": code, "new_password": "short"})
    assert r.status_code == 400 and "8 characters" in r.json()["detail"]

    r = client.post("/auth/reset-password", json={"email": "reset@example.com", "code": code, "new_password": "NewPass!123"})
    assert r.status_code == 200, r.text

    assert client.post("/login", json={"email": "reset@example.com", "password": "OldPass!123"}).status_code == 401
    assert client.post("/login", json={"email": "reset@example.com", "password": "NewPass!123"}).status_code == 200

    # A used code can't be replayed.
    r = client.post("/auth/reset-password", json={"email": "reset@example.com", "code": code, "new_password": "Another!123"})
    assert r.status_code == 400


def test_code_locks_after_too_many_wrong_attempts():
    register_and_login("brute@example.com")
    client.post("/auth/forgot-password", json={"email": "brute@example.com"})
    code = sent["brute@example.com"]
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(auth_routes.MAX_ATTEMPTS):
        client.post("/auth/reset-password", json={"email": "brute@example.com", "code": wrong, "new_password": "NewPass!123"})

    # Even the right code is refused once the attempt limit is hit.
    r = client.post("/auth/reset-password", json={"email": "brute@example.com", "code": code, "new_password": "NewPass!123"})
    assert r.status_code == 400 and r.json()["detail"] == "Invalid or expired code"


def test_new_code_replaces_old_one():
    register_and_login("twice@example.com")
    client.post("/auth/forgot-password", json={"email": "twice@example.com"})
    first = sent["twice@example.com"]
    client.post("/auth/forgot-password", json={"email": "twice@example.com"})
    second = sent["twice@example.com"]

    if first != second:
        r = client.post("/auth/reset-password", json={"email": "twice@example.com", "code": first, "new_password": "NewPass!123"})
        assert r.status_code == 400
    r = client.post("/auth/reset-password", json={"email": "twice@example.com", "code": second, "new_password": "NewPass!123"})
    assert r.status_code == 200
