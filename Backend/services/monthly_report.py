"""Monthly report: facts written by code, commentary by AI (cached).

The "at a glance" section is built from the deterministic summary, so it's
always exact and works even when Gemini is down. Gemini only writes "Buddy's
take" and a few ideas, without numbers, from those facts (never raw notes).
That AI part is cached per month and regenerated only when the facts change.
"""
import hashlib
import json
import logging
import re
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.ai_report_model import AIReport
from models.expense_model import Expense
from services.gemini_client import GeminiUnavailable, generate_json
from services.insight_engine import money, percent
from services.locks import keyed_lock
from services.summary_service import FinancialSummaryGenerator, local_today

logger = logging.getLogger("monthly_report")

NUMBERS = re.compile(r"[0-9₹$%]")

REPORT_PROMPT = """You are Buddy, the friendly money coach in the BudgetBuddy expense tracker.
Here are the facts of the user's {period}, already calculated:
{facts}

Write:
- "take": 2-3 short sentences interpreting how the month went (what stands out, what went well or not).
- "tips": exactly 3 short, specific ideas for next month that would help the user save more or stay
  on budget, each under 18 words, based only on these facts (e.g. which category to watch and how).
  These tips will be shown to the user one at a time as coaching during the next month.
Rules: do NOT include any numbers, amounts, currency symbols or percentages (the user already sees them).
Warm and practical, never judgemental. No markdown. Never invent merchants, events or details.
Return JSON: {{"take": "...", "tips": ["...", "..."]}}"""


def _facts(s: dict) -> list[str]:
    so_far = " so far" if s["is_current_month"] else ""
    facts = []
    if s["monthly_budget"] > 0:
        verdict = ("within budget" if s["remaining_budget"] >= 0
                   else f"{money(-s['remaining_budget'])} over budget")
        facts.append(f"Spent {money(s['total_spent'])} of your {money(s['monthly_budget'])} budget"
                     f"{so_far} ({percent(s['percentage_spent'])}), {verdict}")
    else:
        facts.append(f"Spent {money(s['total_spent'])}{so_far} (no budget set)")

    facts.append(f"{s['expense_count']} expense{'s' * (s['expense_count'] != 1)}, "
                 f"about {money(s['average_daily_spending'])} a day")
    if s["is_current_month"] and s["days_left"] > 1:
        facts.append(f"On course for about {money(s['projected_month_total'])} by month end")

    top = sorted(s["category_totals"].items(), key=lambda kv: kv[1], reverse=True)[:3]
    if top:
        facts.append("Top categories: " + ", ".join(
            f"{name} {money(amount)} ({percent(amount / s['total_spent'] * 100)})" for name, amount in top))

    prev = s["last_month_same_period"] if s["is_current_month"] else s["last_month_total"]
    if prev > 0:
        diff = s["total_spent"] - prev
        when = f"this point in {s['last_month_name']}" if s["is_current_month"] else s["last_month_name"]
        if abs(diff) < 1:
            facts.append(f"About the same as {when}")
        else:
            facts.append(f"{money(abs(diff))} {'more' if diff > 0 else 'less'} than {when}")

    if s["largest_expense_amount"]:
        facts.append(f"Biggest single expense: {money(s['largest_expense_amount'])} ({s['largest_expense_category']})")
    return facts


def _clean(text) -> str | None:
    text = str(text or "").strip()
    return text if text and not NUMBERS.search(text) and len(text) <= 400 else None


def _ai_commentary(period: str, facts: list[str]) -> dict | None:
    try:
        result = generate_json(REPORT_PROMPT.format(period=period, facts="\n".join(f"- {f}" for f in facts)),
                               temperature=0.4)
    except GeminiUnavailable as e:
        logger.warning("Report commentary skipped: %s", e)
        return None
    if not isinstance(result, dict):
        return None
    take = _clean(result.get("take"))
    tips = [t for t in (_clean(t) for t in (result.get("tips") or [])[:3]) if t]
    if not take:
        logger.warning("Report commentary rejected: %r", result)
        return None
    return {"take": take, "tips": tips}


def _fallback_commentary(s: dict) -> dict:
    tips = []
    if s["monthly_budget"] > 0 and s["remaining_budget"] < 0:
        tips.append("Decide which spending is essential before next month starts.")
    if s["top_category"] and s["total_spent"] and s["category_totals"][s["top_category"]] / s["total_spent"] >= 0.4:
        tips.append(f"Set yourself a soft limit for {s['top_category']} next month.")
    tips.append("Keep logging every expense so your next report is just as accurate.")
    return {"take": "Buddy's commentary isn't available right now, but the numbers above are up to date.",
            "tips": tips}


def _save_report(db: Session, user_id: int, year: int, month: int, facts_hash: str, content: dict):
    """Insert or update; if another process inserted first, update its row instead of crashing."""
    values = {"facts_hash": facts_hash, "content": content}
    row = db.query(AIReport).filter(AIReport.user_id == user_id, AIReport.year == year,
                                    AIReport.month == month).first()
    if row:
        row.facts_hash, row.content = facts_hash, content
        db.commit()
        return
    try:
        db.add(AIReport(user_id=user_id, year=year, month=month, **values))
        db.commit()
    except IntegrityError:
        db.rollback()
        db.query(AIReport).filter(AIReport.user_id == user_id, AIReport.year == year,
                                  AIReport.month == month).update(values)
        db.commit()


def build_monthly_report(db: Session, user_id: int, month: int, year: int) -> dict:
    s = FinancialSummaryGenerator.generate_summary(user_id, db, month=month, year=year)
    period = f"{s['current_month']} {year}"

    if s["expense_count"] == 0:
        text = f"{period}\n\nNo expenses logged for this month yet. Add a few and your report will appear here."
        return {"report": text, "facts": [], "take": None, "tips": [], "ai": False}

    facts = _facts(s)
    facts_hash = hashlib.sha256(json.dumps([period, facts]).encode()).hexdigest()

    def cached_report():
        return db.query(AIReport).filter(
            AIReport.user_id == user_id, AIReport.year == year, AIReport.month == month).first()

    cached = cached_report()
    if cached and cached.facts_hash == facts_hash:
        commentary, from_ai = cached.content, True
    else:
        # Only one request per user/month generates; others wait, then reuse its result.
        with keyed_lock(("report", user_id, year, month)):
            db.expire_all()
            cached = cached_report()
            if cached and cached.facts_hash == facts_hash:
                commentary, from_ai = cached.content, True
            else:
                commentary = _ai_commentary(period, facts)
                from_ai = commentary is not None
                if from_ai:
                    _save_report(db, user_id, year, month, facts_hash, commentary)
                else:
                    commentary = _fallback_commentary(s)

    lines = [f"{period} at a glance"] + [f"• {f}" for f in facts]
    lines += ["", "Buddy's take", commentary["take"]]
    if commentary["tips"]:
        lines += ["", "Ideas for next month"] + [f"• {t}" for t in commentary["tips"]]

    return {"report": "\n".join(lines), "facts": facts, "take": commentary["take"],
            "tips": commentary["tips"], "ai": from_ai}


def previous_month(today: date | None = None) -> tuple[int, int]:
    last = (today or local_today()).replace(day=1) - timedelta(days=1)
    return last.year, last.month


def available_report_months(db: Session, user_id: int) -> dict:
    """Months that have at least one expense, newest first, plus which one to show by default.

    Default is last month (its report stays the default for the whole current
    month); if last month had no expenses, the most recent month with data.
    """
    counts: dict[tuple[int, int], int] = {}
    for expense_date, created_at in db.query(Expense.expense_date, Expense.created_at).filter(
            Expense.user_id == user_id).all():
        d = expense_date or created_at.date()
        counts[(d.year, d.month)] = counts.get((d.year, d.month), 0) + 1

    today = local_today()
    months = [{
        "year": y, "month": m, "expense_count": n,
        "label": date(y, m, 1).strftime("%B %Y") + (" (so far)" if (y, m) == (today.year, today.month) else ""),
    } for (y, m), n in sorted(counts.items(), reverse=True)]

    last_year, last_month = previous_month(today)
    default = next((x for x in months if (x["year"], x["month"]) == (last_year, last_month)),
                   months[0] if months else None)
    return {"months": months, "default": {"year": default["year"], "month": default["month"]} if default else None}


def coach_tip_from_last_report(db: Session, user_id: int) -> dict | None:
    """One of last month's report ideas, rotating daily. Reuses cached AI text: no API call."""
    year, month = previous_month()
    report = db.query(AIReport).filter(
        AIReport.user_id == user_id, AIReport.year == year, AIReport.month == month).first()
    tips = (report.content or {}).get("tips") if report else None
    if not tips:
        return None
    tip = tips[local_today().day % len(tips)]
    return {"tip": tip, "source": date(year, month, 1).strftime("%B") + " report"}


def last_month_report_missing(db: Session, user_id: int) -> tuple[int, int] | None:
    """(year, month) if last month had expenses but no cached AI report yet."""
    year, month = previous_month()
    if db.query(AIReport.id).filter(AIReport.user_id == user_id, AIReport.year == year,
                                    AIReport.month == month).first():
        return None
    s = FinancialSummaryGenerator.generate_summary(user_id, db, month=month, year=year)
    return (year, month) if s["expense_count"] else None


def pregenerate_report(user_id: int, year: int, month: int):
    """Background task: build and cache a report so it opens instantly later."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        build_monthly_report(db, user_id, month, year)
    except Exception:
        logger.exception("Pre-generating report %s-%s for user %s failed", year, month, user_id)
    finally:
        db.close()
