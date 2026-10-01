"""Rule-based Coach Insight: picks the most important observation and states it with exact numbers.

No AI and no API calls. Rules are checked in priority order and the first one
that applies wins, so a warning (over budget) always beats a compliment.
Each rule returns a stable `situation` id; the optional AI coach tip is only
regenerated when this id changes (see insight_updater.py).
"""
from datetime import date


def money(value: float) -> str:
    return f"₹{value:,.0f}"


def percent(value: float) -> str:
    if 0 < value < 1:
        return "under 1%"
    if 1 <= value < 10:
        return f"{value:.1f}%"
    return f"{value:.0f}%"


def days(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def _next_month_name(summary: dict) -> str:
    year, month = summary["year"], summary["month"]
    return date(year + (month == 12), month % 12 + 1, 1).strftime("%B")


def build_insight(s: dict) -> dict:
    """Return {"situation", "severity", "insight", "reminder"} for a current-month summary."""
    month = s["current_month"]
    budget = s["monthly_budget"]
    spent = s["total_spent"]
    remaining = s["remaining_budget"]
    days_left = s["days_left"]
    elapsed = s["elapsed_days"]
    safe = s["safe_daily_limit"]
    per_day_tip = f"You can spend up to {money(safe)}/day for the remaining {days(days_left)}."

    # 1. Nothing to measure against yet.
    if budget <= 0:
        if s["expense_count"]:
            return _result("no_budget", "info",
                           f"You've spent {money(spent)} in {month} so far.",
                           "Set a monthly budget to see your pace and daily limit.")
        return _result("no_budget", "info",
                       "Set a monthly budget to get personalised guidance.",
                       "Add your budget from the Budget screen to start tracking.")

    if s["expense_count"] == 0:
        return _result("no_expenses", "info",
                       f"No expenses logged for {month} yet.",
                       f"Your {money(budget)} budget works out to about {money(safe)}/day.")

    # 2. Already over budget.
    if remaining < 0:
        reminder = (f"{_next_month_name(s)} starts tomorrow with a fresh budget." if days_left <= 1
                    else f"Try to keep the remaining {days(days_left)} to essentials only.")
        return _result("over_budget", "critical",
                       f"You're {money(-remaining)} over your {money(budget)} {month} budget.",
                       reminder)

    # 3. Last day of the month: a wrap-up instead of per-day advice.
    if days_left == 1:
        return _result("last_day", "info",
                       f"Last day of {month}: you've used {percent(s['percentage_spent'])} of your budget.",
                       f"You still have {money(remaining)} left if you need it today.")

    # 4. On course to overspend (needs a few days of data to be meaningful).
    projected = s["projected_month_total"]
    if elapsed >= 3 and projected > budget * 1.02:
        return _result("projected_overspend", "warning",
                       f"At {money(s['average_daily_spending'])}/day you're heading for about "
                       f"{money(projected)} this month, {money(projected - budget)} over budget.",
                       f"Keep spending under {money(safe)}/day for the next {days(days_left)} to stay on budget.")

    # 5. Sudden jump in the last week.
    last7, prev7 = s["last_7_days"], s["previous_7_days"]
    if elapsed >= 10 and prev7 > 0 and last7 > prev7 * 1.5 and (last7 - prev7) >= budget * 0.05:
        return _result("weekly_spike", "warning",
                       f"You spent {money(last7)} in the last 7 days, "
                       f"{percent((last7 - prev7) / prev7 * 100)} more than the week before.",
                       per_day_tip)

    # 6. One category dominating.
    top, share = s["top_category"], s["top_category_share"]
    if top and share >= 50 and s["expense_count"] >= 3 and s["top_category_amount"] >= budget * 0.10:
        return _result(f"category_heavy:{top}", "info",
                       f"{top} is {percent(share)} of your {month} spending ({money(s['top_category_amount'])}).",
                       per_day_tip)

    # 7. Spending less than at the same point last month.
    last_month = s["last_month_same_period"]
    if last_month > 0 and spent <= last_month * 0.8:
        return _result("better_than_last_month", "positive",
                       f"You've spent {money(last_month - spent)} less than at this point in {s['last_month_name']}.",
                       per_day_tip)

    # 8. Comfortably under pace.
    month_gone = elapsed / s["days_in_month"] * 100
    if s["percentage_spent"] < month_gone - 10:
        return _result("under_pace", "positive",
                       f"You've used {percent(s['percentage_spent'])} of your budget with "
                       f"{percent(month_gone)} of {month} gone. Nicely under pace.",
                       per_day_tip)

    # 9. Roughly on pace.
    return _result("on_pace", "info",
                   f"You've used {percent(s['percentage_spent'])} of your budget with {days(days_left)} of {month} to go.",
                   per_day_tip)


def _result(situation: str, severity: str, insight: str, reminder: str) -> dict:
    return {"situation": situation, "severity": severity, "insight": insight, "reminder": reminder}
