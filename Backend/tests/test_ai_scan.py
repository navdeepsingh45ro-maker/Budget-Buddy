"""Receipt scan and voice parse routes, with Gemini replaced by a stub."""
import pytest

from tests.test_smoke import client, register_and_login

import services.gemini_parser as gemini_parser
import services.receipt_scanner as receipt_scanner
from services.gemini_client import GeminiUnavailable

JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


@pytest.fixture(scope="module")
def auth():
    return register_and_login("scanner@example.com")


def stub_gemini(monkeypatch, module, reply):
    def fake(contents):
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(module, "generate_json", fake)


def upload(headers, data=JPEG, content_type="image/jpeg"):
    return client.post("/ai/scan-receipt", files={"file": ("receipt.jpg", data, content_type)}, headers=headers)


def test_scan_requires_login():
    assert upload({}).status_code == 401


def test_scan_rejects_non_images(auth):
    r = upload(auth, b"%PDF-1.4", "application/pdf")
    assert r.status_code == 400


def test_scan_returns_cleaned_fields(auth, monkeypatch):
    stub_gemini(monkeypatch, receipt_scanner, {
        "is_receipt": True, "amount": "764.40", "currency": "INR", "category": "Food",
        "subcategory": "Domino's Pizza MG Road Branch", "note": "Pizza, garlic bread",
        "payment_method": "GPay", "expense_date": "2026-01-15", "confidence": 1.7,
    })
    r = upload(auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amount"] == 764.4
    assert body["category"] == "Food"
    assert body["subcategory"] == "Domino's Pizza MG"     # trimmed to 3 words
    assert body["payment_method"] == "UPI"                 # GPay alias
    assert body["expense_date"] == "2026-01-15"
    assert body["confidence"] == 1.0                       # clamped


def test_scan_drops_bad_category_and_future_date(auth, monkeypatch):
    stub_gemini(monkeypatch, receipt_scanner, {
        "is_receipt": True, "amount": 99, "category": "Snacks", "expense_date": "2999-01-01",
    })
    body = upload(auth).json()
    assert body["category"] == "Other"
    assert body["expense_date"] is None


def test_scan_non_receipt_is_422(auth, monkeypatch):
    stub_gemini(monkeypatch, receipt_scanner, {"is_receipt": False, "amount": None})
    r = upload(auth)
    assert r.status_code == 422
    assert "Couldn't read a total" in r.json()["detail"]


def test_scan_ai_down_is_503(auth, monkeypatch):
    stub_gemini(monkeypatch, receipt_scanner, GeminiUnavailable("all models busy"))
    r = upload(auth)
    assert r.status_code == 503
    assert "busy" in r.json()["detail"]


def test_voice_parse_uses_same_cleanup(auth, monkeypatch):
    stub_gemini(monkeypatch, gemini_parser, {
        "amount": 450, "category": "Food", "subcategory": "Domino's",
        "payment_method": "upi", "confidence": 0.9,
    })
    r = client.post("/ai/parse-expense", json={"text": "Spent 450 on Domino's using UPI"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["amount"] == 450 and body["payment_method"] == "UPI"
    assert body["note"] == "Spent 450 on Domino's using UPI"


def test_voice_parse_ai_down_is_503(auth, monkeypatch):
    stub_gemini(monkeypatch, gemini_parser, GeminiUnavailable("down"))
    r = client.post("/ai/parse-expense", json={"text": "coffee 120"}, headers=auth)
    assert r.status_code == 503
