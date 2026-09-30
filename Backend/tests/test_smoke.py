"""End-to-end smoke test of the core flow: auth, budget, expense CRUD, ownership.

Run from the Backend folder:  python3 -m pytest tests -q
(tests/conftest.py points every test at a throwaway database.)
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def register_and_login(email, password="Str0ng!pass"):
    r = client.post("/users/", json={"name": "Test", "email": email, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health():
    assert client.get("/").status_code == 200


def test_auth_rejects_bad_credentials_and_missing_token():
    register_and_login("wrongpass@example.com")
    r = client.post("/login", json={"email": "wrongpass@example.com", "password": "nope"})
    assert r.status_code == 401
    assert client.get("/expenses").status_code == 401


def test_me_does_not_leak_password_hash():
    headers = register_and_login("me@example.com")
    body = client.get("/users/me", headers=headers).json()
    assert body["email"] == "me@example.com"
    assert "password" not in body


def test_budget_and_expense_lifecycle():
    headers = register_and_login("alice@example.com")

    assert client.post("/budget/", json={"monthly_budget": 20000}, headers=headers).status_code == 200
    assert client.get("/budget/", headers=headers).json()["monthly_budget"] == 20000

    r = client.post("/expense/", json={"amount": 250, "category": "Food", "note": "Lunch"}, headers=headers)
    assert r.status_code == 200, r.text

    expenses = client.get("/expenses", headers=headers).json()
    assert len(expenses) == 1
    expense_id = expenses[0]["id"]

    r = client.put(f"/expense/{expense_id}", json={"amount": 300, "category": "Food", "note": "Lunch"}, headers=headers)
    assert r.status_code == 200, r.text
    assert client.get("/expenses", headers=headers).json()[0]["amount"] == 300

    assert client.get("/analytics", headers=headers).status_code == 200

    assert client.delete(f"/expense/{expense_id}", headers=headers).status_code == 200
    assert client.get("/expenses", headers=headers).json() == []


def test_users_cannot_touch_each_others_expenses():
    owner = register_and_login("owner@example.com")
    intruder = register_and_login("intruder@example.com")

    client.post("/expense/", json={"amount": 99, "category": "Bills"}, headers=owner)
    expense_id = client.get("/expenses", headers=owner).json()[0]["id"]

    assert client.get("/expenses", headers=intruder).json() == []
    assert client.put(f"/expense/{expense_id}", json={"amount": 1, "category": "Bills"}, headers=intruder).status_code == 404
    assert client.delete(f"/expense/{expense_id}", headers=intruder).status_code == 404
    assert client.get("/expenses", headers=owner).json()[0]["amount"] == 99
