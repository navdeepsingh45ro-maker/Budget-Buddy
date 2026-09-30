"""Read a receipt photo with Gemini and turn it into expense form fields."""
import logging
from datetime import date

from google.genai import types

from services.gemini_client import generate_json
from services.gemini_parser import normalize_expense

logger = logging.getLogger("receipt_scanner")

RECEIPT_PROMPT = """You are reading a photo of a purchase receipt or bill. Extract the expense as a single JSON object with exactly these keys:
- "is_receipt": true if the image shows a receipt, bill or invoice, otherwise false
- "amount": number or null. The FINAL amount paid (grand total including tax, after discounts). Not a subtotal, not a single item.
- "currency": string or null (e.g. "INR", "USD")
- "category": string or null, one of: Food, Transport, Entertainment, Shopping, Bills, Health, Education, Subscriptions, EMI Loans, Rent, Investments, Savings, Travel, Family, Personal Care, Gifts, Donations, Insurance, Taxes, Other
- "subcategory": string or null. The merchant or store name, max 3 words.
- "note": string or null. A short description like "Domino's: pizza, garlic bread, drinks" (max 80 characters).
- "payment_method": string or null, one of: Cash, Card, UPI, Bank Transfer. Only if the receipt shows it.
- "expense_date": string or null. The receipt date as YYYY-MM-DD. Receipts from India usually write dates as DD/MM/YYYY.
- "confidence": number between 0 and 1

Never invent values. If something is unreadable, use null."""


def scan_receipt(image_bytes: bytes, mime_type: str) -> dict:
    parsed = generate_json([
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        RECEIPT_PROMPT,
    ])
    if not isinstance(parsed, dict):
        parsed = {}

    result = normalize_expense(parsed, fallback_note=None)

    # A date in the future is a misread (e.g. day and month swapped).
    if result["expense_date"] and result["expense_date"] > date.today().isoformat():
        result["expense_date"] = None

    result["is_receipt"] = bool(parsed.get("is_receipt", True))
    result["currency"] = parsed.get("currency")
    if result["note"]:
        result["note"] = str(result["note"])[:120]

    logger.info("Receipt scanned: merchant=%s amount=%s", result["subcategory"], result["amount"])
    return result
