"""Web Push delivery: sends saved notifications to the user's devices.

Every notification is still saved for the in-app bell drawer. Whether it is
ALSO pushed to devices depends on its origin, chosen where it is created:

| push_origin  | Meaning                                                   | Pushed?               |
|--------------|-----------------------------------------------------------|-----------------------|
| "user_setup" | Comes from something the user set up (recurring bills,    | Always, even at night |
|              | budget alerts caused by those bills)                      |                       |
| "app"        | The app's own messages (reminders, summaries, reports,    | Daytime only; at night|
|              | Buddy's alerts)                                           | it stays in the drawer|
| None         | Caused by the user while using the app (e.g. adding an    | Never                 |
|              | expense that crosses 80%), or not worth a buzz            |                       |

Sending happens on a background thread so saving a notification never waits
on Apple/Google/Mozilla push servers. Devices that no longer exist (the push
service answers 404/410) are removed automatically.
"""
import json
import logging
import os
import threading
from datetime import datetime

from pywebpush import WebPushException, webpush

from database import SessionLocal
from models.notification_model import Notification
from models.push_subscription_model import PushSubscription
from services.summary_service import APP_TIMEZONE

logger = logging.getLogger("push_service")

QUIET_START_HOUR = 22   # 10 PM
QUIET_END_HOUR = 8      # 8 AM
MAX_FAILURES = 5        # drop a device after this many consecutive errors
TTL_SECONDS = 24 * 3600 # push services keep undelivered messages for a day

USER_SETUP = "user_setup"
APP = "app"


def is_configured() -> bool:
    return bool(os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_PRIVATE_KEY"))


def public_key() -> str | None:
    return os.getenv("VAPID_PUBLIC_KEY")


def is_quiet_hours(now: datetime | None = None) -> bool:
    hour = (now or datetime.now(APP_TIMEZONE)).hour
    return hour >= QUIET_START_HOUR or hour < QUIET_END_HOUR


def should_push(origin: str | None, now: datetime | None = None) -> bool:
    if origin == USER_SETUP:
        return True
    if origin == APP:
        return not is_quiet_hours(now)
    return False


def _run_in_background(fn, *args):
    """Separate function so tests can run deliveries synchronously."""
    threading.Thread(target=fn, args=args, daemon=True).start()


def dispatch(notification_id: int, origin: str | None):
    """Called right after a notification is saved. Decides, then sends in the background."""
    if not is_configured() or not should_push(origin):
        return
    _run_in_background(deliver, notification_id)


def _payload(n: Notification) -> dict:
    return {
        "title": n.title,
        "body": n.message,
        "tag": f"bb-{n.id}",                 # same tag = replaces, never duplicates
        "notification_id": n.id,
        "action_type": n.action_type,
        "action_payload": n.action_payload,
        "priority": n.priority,
    }


def deliver(notification_id: int) -> int:
    """Send one saved notification to all of its user's devices. Returns devices reached."""
    db = SessionLocal()
    try:
        n = db.query(Notification).filter(Notification.id == notification_id).first()
        if not n:
            return 0
        return send_to_user(db, n.user_id, _payload(n))
    except Exception:
        logger.exception("Push delivery failed for notification %s", notification_id)
        return 0
    finally:
        db.close()


def send_to_user(db, user_id: int, payload: dict) -> int:
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=json.dumps(payload),
                vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"),
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:support@budgetbuddy.app")},
                ttl=TTL_SECONDS,
            )
            sub.failure_count = 0
            sub.last_success_at = datetime.utcnow()
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                logger.info("Removing expired push subscription %s (HTTP %s)", sub.id, status)
                db.delete(sub)
            else:
                sub.failure_count += 1
                logger.warning("Push to subscription %s failed (HTTP %s): %s", sub.id, status, e)
                if sub.failure_count >= MAX_FAILURES:
                    db.delete(sub)
        except Exception:
            sub.failure_count += 1
            logger.exception("Unexpected push error for subscription %s", sub.id)
    db.commit()
    return sent
