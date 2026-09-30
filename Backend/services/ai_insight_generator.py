"""Optional AI coach tip: one friendly sentence that complements the rule-based insight.

The tip deliberately contains no numbers. All figures come from the rule engine,
so they are always exact and current; the AI only adds tone and a practical idea.
Any tip containing digits, currency or percentages is rejected.
"""
import logging
import re

from services.gemini_client import GeminiUnavailable, generate_json

logger = logging.getLogger("ai_insight_generator")

COACH_TIP_PROMPT = """You are Buddy, the friendly money coach inside the BudgetBuddy expense tracker.
The app has already shown the user this insight, with exact figures:
  "{insight}"
Situation: {situation} (severity: {severity}). Month: {month}. Top spending category: {top_category}.

Write ONE short coaching tip that fits this situation.
Rules:
- Maximum 20 words, one sentence, warm and practical, never guilt-tripping.
- Do NOT include any numbers, amounts, currency symbols or percentages.
- Do NOT repeat the insight; add a helpful idea or encouragement instead.
- Only refer to facts given above; never invent merchants, events or details.
Return JSON: {{"tip": "..."}}"""

NUMBERS = re.compile(r"[0-9₹$%]")


def generate_coach_tip(insight: dict, summary: dict) -> str | None:
    """Return a validated tip, or None if the AI is unavailable or breaks the rules."""
    prompt = COACH_TIP_PROMPT.format(
        insight=insight["insight"],
        situation=insight["situation"],
        severity=insight["severity"],
        month=summary["current_month"],
        top_category=summary.get("top_category") or "none yet",
    )
    try:
        result = generate_json(prompt)
    except GeminiUnavailable as e:
        logger.warning("Coach tip skipped: %s", e)
        return None

    tip = str(result.get("tip", "")).strip() if isinstance(result, dict) else ""
    if not tip or NUMBERS.search(tip) or len(tip) > 160:
        logger.warning("Coach tip rejected: %r", tip)
        return None
    return tip
