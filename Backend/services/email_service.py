"""Outgoing transactional email (password-reset and sign-up confirmation codes only).

Two ways to send, chosen by what is set in Backend/.env:

1. Brevo's HTTPS API (use this on the live server). Free hosts such as Render's
   free plan block the SMTP ports, so Gmail SMTP cannot work there.
       BREVO_API_KEY=<key from brevo.com: SMTP & API > API keys>
       EMAIL_FROM="Budget Buddy <you@gmail.com>"   (an address verified as a sender in Brevo)

2. SMTP, Gmail by default (fine on your own computer or a paid server).
       SMTP_HOST=smtp.gmail.com
       SMTP_PORT=587
       SMTP_USER=you@gmail.com
       SMTP_PASSWORD=<16-character Gmail App Password>
       EMAIL_FROM="Budget Buddy <you@gmail.com>"   (optional, defaults to SMTP_USER)

If neither is set (local development), nothing is sent.
"""
import html as html_lib
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

logger = logging.getLogger("email_service")

BRAND_PRIMARY = "#66547b"
BRAND_BACKGROUND = "#fef8fb"
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _use_brevo() -> bool:
    return bool(os.getenv("BREVO_API_KEY") and os.getenv("EMAIL_FROM"))


def is_configured() -> bool:
    return _use_brevo() or bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _send_via_brevo(to: str, subject: str, text: str, html: str | None) -> bool:
    sender_name, sender_email = parseaddr(os.getenv("EMAIL_FROM"))
    body = {
        "sender": {"name": sender_name or "Budget Buddy", "email": sender_email},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
    }
    if html:
        body["htmlContent"] = html
    request = urllib.request.Request(
        BREVO_URL, data=json.dumps(body).encode(), method="POST",
        headers={"api-key": os.getenv("BREVO_API_KEY"), "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as e:
        # Status only: the response and request bodies can contain the recipient and the code.
        logger.error("Email provider refused the message (HTTP %s).", e.code)
        return False
    except Exception:
        logger.exception("Failed to send email.")
        return False


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    if not is_configured():
        # Never log the recipient, subject or body: reset codes appear in both.
        logger.warning("Email is not configured; email not sent.")
        return False
    if _use_brevo():
        return _send_via_brevo(to, subject, text, html)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER")
    msg["To"] = to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
            smtp.starttls()
            # Gmail shows app passwords in groups of four; the spaces aren't part of it.
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD").replace(" ", ""))
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email.")
        return False


# TRANSACTIONAL EMAIL
# This function sends a transactional (non-marketing) email and is exempt from CAN-SPAM
# and other marketing-email rules. Do NOT add promotions, newsletters, or other marketing
# content to this function. Any future marketing email must be a separate function with
# an unsubscribe link, a postal address, List-Unsubscribe headers, and suppression list checks.
def send_password_reset_code(to: str, name: str, code: str, minutes_valid: int) -> bool:
    subject = f"Your Budget Buddy reset code: {code}"
    text = (
        f"Hi {name},\n\n"
        f"Your Budget Buddy password reset code is {code}.\n"
        f"It expires in {minutes_valid} minutes.\n\n"
        "If you didn't ask to reset your password, you can ignore this email."
    )
    safe_name = html_lib.escape(name)
    html = f"""\
<div style="background:{BRAND_BACKGROUND};padding:32px 16px;font-family:Arial,sans-serif;color:#1d1b1e">
  <div style="max-width:420px;margin:0 auto;background:#ffffff;border-radius:24px;padding:32px;text-align:center">
    <h1 style="color:{BRAND_PRIMARY};font-size:22px;margin:0 0 8px">Budget Buddy</h1>
    <p style="margin:0 0 24px">Hi {safe_name}, here is your password reset code:</p>
    <div style="font-size:34px;letter-spacing:8px;font-weight:bold;color:{BRAND_PRIMARY};margin-bottom:24px">{code}</div>
    <p style="font-size:13px;color:#4a454e;margin:0">It expires in {minutes_valid} minutes.<br>
    If you didn't ask to reset your password, you can ignore this email.</p>
  </div>
</div>"""
    return send_email(to, subject, text, html)


# TRANSACTIONAL EMAIL (same rules as above: never add marketing content).
def send_verification_code(to: str, name: str, code: str, minutes_valid: int) -> bool:
    subject = "Confirm your email for Budget Buddy"
    text = (
        f"Hi {name},\n\n"
        f"Your Budget Buddy confirmation code is {code}.\n"
        f"It expires in {minutes_valid} minutes.\n\n"
        "If you didn't sign up for Budget Buddy, you can ignore this email and no account will be kept."
    )
    safe_name = html_lib.escape(name)
    html = f"""\
<div style="background:{BRAND_BACKGROUND};padding:32px 16px;font-family:Arial,sans-serif;color:#1d1b1e">
  <div style="max-width:420px;margin:0 auto;background:#ffffff;border-radius:24px;padding:32px;text-align:center">
    <h1 style="color:{BRAND_PRIMARY};font-size:22px;margin:0 0 8px">Budget Buddy</h1>
    <p style="margin:0 0 24px">Hi {safe_name}, confirm your email with this code:</p>
    <div style="font-size:34px;letter-spacing:8px;font-weight:bold;color:{BRAND_PRIMARY};margin-bottom:24px">{code}</div>
    <p style="font-size:13px;color:#4a454e;margin:0">It expires in {minutes_valid} minutes.<br>
    If you didn't sign up, you can ignore this email and no account will be kept.</p>
  </div>
</div>"""
    return send_email(to, subject, text, html)

