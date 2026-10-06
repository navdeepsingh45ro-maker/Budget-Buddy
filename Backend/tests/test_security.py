"""Security checks: brute-force limits, session invalidation, input limits, export safety."""
from tests.test_smoke import client, register_and_login

from routes import user_routes
from services.export.provider_interface import safe_cell


def test_login_locks_after_repeated_failures_then_recovers():
    register_and_login("lock@example.com", password="RightPass1")
    for _ in range(user_routes.LOGIN_PER_EMAIL.max_events):
        assert client.post("/login", json={"email": "lock@example.com", "password": "wrong"}).status_code == 401
    # Locked: even the right password is refused, and the reply says to wait.
    r = client.post("/login", json={"email": "LOCK@example.com ", "password": "RightPass1"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    # Other accounts are unaffected.
    register_and_login("bystander@example.com")
    user_routes.LOGIN_PER_EMAIL.reset("lock@example.com")
    assert client.post("/login", json={"email": "lock@example.com", "password": "RightPass1"}).status_code == 200


def test_signup_is_limited_per_network():
    for i in range(user_routes.SIGNUP_PER_IP.max_events):
        register_and_login(f"bulk{i}@example.com")
    r = client.post("/users/", json={"name": "N", "email": "bulk-extra@example.com", "password": "Longenough1",
                                     "age_group": "18_plus", "accept_terms": True})
    assert r.status_code == 429


def test_email_is_case_insensitive_everywhere():
    register_and_login("Mixed.Case@Example.com")
    assert client.post("/login", json={"email": "mixed.case@example.com", "password": "Str0ng!pass"}).status_code == 200
    r = client.post("/users/", json={"name": "Dup", "email": "MIXED.CASE@example.com", "password": "Longenough1",
                                     "age_group": "18_plus", "accept_terms": True})
    assert r.status_code == 400


def test_password_change_signs_out_old_sessions():
    old = register_and_login("rotate@example.com", password="FirstPass1")
    r = client.post("/users/me/password", headers=old, json={"current_password": "FirstPass1", "new_password": "SecondPass2"})
    assert r.status_code == 200
    assert client.get("/users/me", headers=old).status_code == 401           # stolen/old token is dead
    fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/users/me", headers=fresh).status_code == 200         # this device stays logged in


def test_password_guessing_with_a_session_is_limited():
    headers = register_and_login("guess@example.com", password="RightPass1")
    for _ in range(user_routes.PASSWORD_CHECK_PER_USER.max_events):
        assert client.post("/users/me/delete", headers=headers, json={"password": "nope"}).status_code == 400
    assert client.post("/users/me/delete", headers=headers, json={"password": "RightPass1"}).status_code == 429
    assert client.get("/users/me", headers=headers).status_code == 200       # account still exists


def test_forgot_password_never_reveals_an_account():
    register_and_login("exists@example.com")
    replies = set()
    for _ in range(7):  # more than the per-account email limit
        r = client.post("/auth/forgot-password", json={"email": "exists@example.com"})
        replies.add((r.status_code, r.json()["message"]))
    r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    replies.add((r.status_code, r.json()["message"]))
    assert len(replies) == 1


def test_oversized_and_invalid_input_is_rejected():
    headers = register_and_login("limits@example.com")
    base = {"amount": 100, "category": "Food"}
    assert client.post("/expense/", headers=headers, json={**base, "note": "x" * 501}).status_code == 422
    assert client.post("/expense/", headers=headers, json={**base, "amount": 1e12}).status_code == 422
    assert client.post("/expense/", headers=headers, json={**base, "expense_date": "1800-01-01"}).status_code == 422
    assert client.post("/ai/parse-expense", headers=headers, json={"text": "x" * 501}).status_code == 422
    assert client.get("/expenses/query?limit=100000", headers=headers).status_code == 422
    assert client.get("/expenses/query?start_date=not-a-date", headers=headers).status_code == 400
    assert client.post("/login", json={"email": "limits@example.com", "password": "x" * 5000}).status_code == 422


def test_other_users_data_is_unreachable():
    owner, intruder = register_and_login("owner2@example.com"), register_and_login("intruder2@example.com")
    expense_id = client.post("/expense/", headers=owner, json={"amount": 50, "category": "Food", "note": "private"}).json()["id"]
    rt = client.post("/recurring/", headers=owner, json={"title": "Rent", "amount": 1, "category": "Rent",
                                                         "frequency": "monthly", "start_date": "2026-01-01"}).json()
    rt_id = rt.get("id") or rt.get("recurring", {}).get("id")
    note_id = client.get("/notifications/", headers=owner).json()["notifications"][0]["id"]

    assert client.put(f"/expense/{expense_id}", headers=intruder, json={"amount": 1, "category": "Food"}).status_code == 404
    assert client.delete(f"/expense/{expense_id}", headers=intruder).status_code == 404
    assert client.get(f"/recurring/{rt_id}", headers=intruder).status_code == 404
    assert client.put(f"/recurring/{rt_id}", headers=intruder, json={"title": "x"}).status_code == 404
    assert client.delete(f"/recurring/{rt_id}", headers=intruder).status_code == 404
    assert client.patch(f"/notifications/{note_id}/read", headers=intruder).status_code == 404
    assert client.delete(f"/notifications/{note_id}", headers=intruder).status_code == 404
    assert "private" not in client.get("/expenses", headers=intruder).text
    assert "private" not in client.get("/export/csv", headers=intruder).text


def test_export_neutralises_spreadsheet_formulas():
    assert safe_cell("=HYPERLINK(\"http://evil\")").startswith("'=")
    assert safe_cell("+1") == "'+1" and safe_cell("@x") == "'@x" and safe_cell("Lunch") == "Lunch" and safe_cell(None) == ""
    headers = register_and_login("csv@example.com")
    client.post("/expense/", headers=headers, json={"amount": 5, "category": "Food", "note": "=1+1"})
    assert "'=1+1" in client.get("/export/csv", headers=headers).text


def test_security_headers_present():
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Cache-Control"] == "no-store"
