import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from services.gemini_client import generate_json

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ── Logging ─────────────────────────────────────────────────────
logger = logging.getLogger("gemini_parser")
logging.basicConfig(level=logging.INFO)

# ── Valid Values (synced with expense_schema.py) ────────────────
VALID_CATEGORIES = {
    "Food", "Transport", "Entertainment", "Shopping", "Bills",
    "Health", "Education", "Subscriptions", "EMI Loans", "Rent",
    "Investments", "Savings", "Travel", "Family", "Personal Care",
    "Gifts", "Donations", "Insurance", "Taxes", "Other"
}

VALID_PAYMENT_METHODS = {"Cash", "Card", "UPI", "Bank Transfer"}

# Normalize common Gemini responses to valid payment methods
PAYMENT_METHOD_ALIASES = {
    "cash": "Cash",
    "card": "Card",
    "credit card": "Card",
    "debit card": "Card",
    "visa": "Card",
    "mastercard": "Card",
    "rupay": "Card",
    "upi": "UPI",
    "gpay": "UPI",
    "google pay": "UPI",
    "phonepe": "UPI",
    "paytm": "UPI",
    "bank transfer": "Bank Transfer",
    "neft": "Bank Transfer",
    "imps": "Bank Transfer",
    "rtgs": "Bank Transfer",
}

# ── Prompt (single source of truth) ────────────────────────────
EXPENSE_PARSER_PROMPT = """You are a strict JSON expense parser. Parse the following expense text into structured data.

Return ONLY a single JSON object with these exact keys:
- "amount": number or null (extract the numeric amount)
- "category": string or null (one of: Food, Transport, Entertainment, Shopping, Bills, Health, Education, Subscriptions, EMI Loans, Rent, Investments, Savings, Travel, Family, Personal Care, Gifts, Donations, Insurance, Taxes, Other)
- "subcategory": string or null (specific merchant, brand, or service name, max 3 words)
- "note": string or null (the original expense description cleaned up)
- "payment_method": string or null (one of: Cash, Card, UPI, Bank Transfer, or null if not mentioned)
- "expense_date": string or null (ISO format YYYY-MM-DD if a date is mentioned, otherwise null)
- "confidence": number between 0 and 1 (how confident you are in the parsing)

Rules:
- Return ONLY valid JSON. No explanation. No markdown. No code fences.
- If a value cannot be determined, set it to null.
- Never wrap the response in ```json``` or any other formatting.
- Never guess. If uncertain, return null. Do not invent values.

Text to parse:
"""


def normalize_expense(parsed: dict, fallback_note: str | None) -> dict:
    """Validate Gemini's raw fields into values the expense form accepts."""
    # Category: whitelist check
    category = parsed.get("category")
    if category not in VALID_CATEGORIES:
        category = "Other"

    # Payment method: normalize aliases
    raw_payment = parsed.get("payment_method")
    payment_method = None
    if isinstance(raw_payment, str) and raw_payment.strip():
        payment_method = PAYMENT_METHOD_ALIASES.get(raw_payment.lower().strip())
        if payment_method is None and raw_payment in VALID_PAYMENT_METHODS:
            payment_method = raw_payment

    # Confidence: clamp to 0-1
    try:
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))

    # Date: validate YYYY-MM-DD format
    expense_date = parsed.get("expense_date")
    if expense_date:
        try:
            datetime.strptime(str(expense_date), "%Y-%m-%d")
        except ValueError:
            expense_date = None

    # Amount: validate and convert to float
    amount = parsed.get("amount")
    try:
        amount = round(float(amount), 2)
        if amount <= 0:
            amount = None
    except (TypeError, ValueError):
        amount = None

    # Subcategory: limit to 3 words
    subcategory = parsed.get("subcategory")
    if isinstance(subcategory, str) and subcategory.strip():
        subcategory = " ".join(subcategory.split()[:3])
    else:
        subcategory = None

    return {
        "amount": amount,
        "category": category,
        "subcategory": subcategory,
        "note": parsed.get("note") or fallback_note,
        "payment_method": payment_method,
        "expense_date": expense_date,
        "confidence": confidence,
    }


class GeminiParser:

    def parse_expense(self, text: str) -> dict:
        """
        Accepts a natural language expense string and returns structured
        expense fields, e.g. "Spent 450 rupees on Domino's using UPI" ->
        {"amount": 450, "category": "Food", "subcategory": "Domino's", ...}
        """
        parsed = generate_json(EXPENSE_PARSER_PROMPT + f'"{text}"')
        if not isinstance(parsed, dict):
            logger.warning(f"Gemini returned unexpected response: {parsed!r}")
            parsed = {}

        result = normalize_expense(parsed, fallback_note=text)
        logger.info(f"Transcript: {text}")
        logger.info(f"Parsed: {json.dumps(result, indent=2)}")
        return result


# ── Quick test ──────────────────────────────────────────────────
if __name__ == "__main__":
    parser = GeminiParser()
    test_inputs = [
        "Spent 450 rupees on Domino's using UPI",
        "Paid 120 for petrol",
        "Netflix subscription 199 from card",
        "Gave 2000 to dad",
        "Uber ride to office 250 cash",
    ]
    for text in test_inputs:
        print(f"\nInput: {text}")
        result = parser.parse_expense(text)
        print(json.dumps(result, indent=2))


