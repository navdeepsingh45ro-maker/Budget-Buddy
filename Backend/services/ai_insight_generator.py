import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("ai_insight_generator")
logging.basicConfig(level=logging.INFO)

AI_INSIGHT_PROMPT = """You are Buddy, the financial assistant inside BudgetBuddy.
Your task is to provide one personalized insight and one actionable reminder based ONLY on the provided financial summary.

Return ONLY a single valid JSON object with these exact keys:
{
  "insight": "A factual, personalized statement under 30 words about the user's spending. Never exaggerate or invent data.",
  "reminder": "An actionable, data-driven tip under 20 words based on the summary. Never guilt the user or invent advice."
}

Strict Rules:
1. Avoid repeating the same type of observation every time.
2. Prioritize the most useful financial observation available from the summary.
3. Rotate between:
   - budget progress
   - spending pace
   - category concentration
   - remaining budget
   - daily safe spending
4. Only mention one primary observation.
5. Return ONLY raw valid JSON. Do NOT use markdown code blocks (no ```json or ```).
6. No greetings, conversational text, explanations, or extra keys.
7. If no budget is set (monthly_budget is 0), set insight to "Set a monthly budget to receive personalized guidance." and reminder to "Set a budget from the overview screen to start tracking."
8. If no expenses recorded (expense_count is 0), set insight to "No expenses recorded for this month yet." and reminder to "Log your first expense to start tracking your spending."
9. Never invent facts, merchants, or details not present in the summary. For example, instead of saying 'try cooking at home', say 'Keeping spending below ₹X/day would keep you on track.'

Financial Summary Data:
"""


class AIInsightGenerator:
    """
    Generates personalized insights and reminders using Gemini 3.5 Flash,
    consuming ONLY structured financial summaries. Never processes raw transaction history.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_insight(self, summary: dict) -> dict:
        """
        Accepts a financial summary dictionary and returns a JSON dict with 'insight' and 'reminder'.
        """
        monthly_budget = summary.get("monthly_budget", 0.0)
        expense_count = summary.get("expense_count", 0)

        # Edge case 1: No budget set
        if monthly_budget == 0.0:
            return {
                "insight": "Set a monthly budget to receive personalized guidance.",
                "reminder": "Set a budget from the overview screen to start tracking."
            }

        # Edge case 2: No expenses
        if expense_count == 0:
            return {
                "insight": "No expenses recorded for this month yet.",
                "reminder": "Log your first expense to start tracking your spending."
            }

        remaining = summary.get("remaining_budget", 0.0)
        days_left = summary.get("days_left", 0)
        daily_safe_limit = round(remaining / days_left, 2) if days_left > 0 and remaining > 0 else 0.0

        pct_spent = summary.get("percentage_spent", 0.0)
        if pct_spent > 100:
            budget_status = "over_budget"
        elif pct_spent >= 80:
            budget_status = "caution"
        else:
            budget_status = "on_track"

        context_summary = {
            "current_month": summary.get("current_month"),
            "monthly_budget": monthly_budget,
            "total_spent": summary.get("total_spent"),
            "remaining_budget": remaining,
            "percentage_spent": pct_spent,
            "top_category": summary.get("top_category"),
            "top_category_amount": summary.get("top_category_amount"),
            "expense_count": expense_count,
            "average_daily_spending": summary.get("average_daily_spending"),
            "days_left": days_left,
            "daily_safe_limit": daily_safe_limit,
            "budget_status": budget_status
        }

        prompt = AI_INSIGHT_PROMPT + json.dumps(context_summary, indent=2)
        raw = ""

        try:
            config = genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=500
            )

            response = self.model.generate_content(prompt, generation_config=config)
            if response and hasattr(response, 'text'):
                raw = response.text.strip()

            # Clean markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

            result = json.loads(raw)
            if "insight" in result and "reminder" in result:
                return {
                    "insight": str(result["insight"]).strip(),
                    "reminder": str(result["reminder"]).strip()
                }

            raise ValueError("Missing required keys in AI response")

        except Exception as e:
            logger.warning(f"AI insight generation failed ({e}). Using deterministic fallback.")
            if budget_status == "over_budget":
                return {
                    "insight": f"You've exceeded your monthly budget by ₹{abs(remaining):,.0f}.",
                    "reminder": "Pause non-essential spending for the remainder of the month."
                }
            elif budget_status == "caution":
                return {
                    "insight": f"You have used {pct_spent}% of your budget with {days_left} days remaining.",
                    "reminder": f"Keep daily spending under ₹{daily_safe_limit:,.0f} to stay within budget."
                }
            else:
                return {
                    "insight": f"You have used {pct_spent}% of your budget so far in {summary.get('current_month')}.",
                    "reminder": f"You have ₹{daily_safe_limit:,.0f}/day available for the remaining {days_left} days."
                }
