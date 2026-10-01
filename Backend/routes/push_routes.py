"""Register and remove this device for push notifications."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.auth2 import get_current_user
from database import get_db
from models.push_subscription_model import PushSubscription
from models.user_model import User
from services import push_service

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(..., max_length=255)
    auth: str = Field(..., max_length=255)


class SubscribeRequest(BaseModel):
    """The browser's PushSubscription.toJSON() (expirationTime is ignored)."""
    endpoint: str = Field(..., max_length=1000)
    keys: SubscriptionKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., max_length=1000)


@router.get("/public-key")
def get_public_key():
    if not push_service.is_configured():
        raise HTTPException(status_code=503, detail="Push notifications aren't set up on the server yet.")
    return {"public_key": push_service.public_key()}


@router.post("/subscribe")
def subscribe(body: SubscribeRequest, request: Request, current_user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if not body.endpoint.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid push subscription.")
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if sub:
        # Same device: refresh keys, and move it to whoever is logged in now.
        sub.user_id, sub.p256dh, sub.auth, sub.failure_count = current_user.id, body.keys.p256dh, body.keys.auth, 0
    else:
        db.add(PushSubscription(user_id=current_user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh,
                                auth=body.keys.auth, user_agent=(request.headers.get("user-agent") or "")[:300]))
    db.commit()
    return {"message": "Push notifications are on for this device."}


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeRequest, current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint,
                                      PushSubscription.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Push notifications are off for this device."}


@router.post("/test")
def send_test(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a test push to all of the user's devices right away (ignores quiet hours)."""
    if not push_service.is_configured():
        raise HTTPException(status_code=503, detail="Push notifications aren't set up on the server yet.")
    sent = push_service.send_to_user(db, current_user.id, {
        "title": "Budget Buddy notifications are on",
        "body": "This is a test. Reminders and alerts will arrive here.",
        "tag": "bb-test",
        "action_type": None,
    })
    if not sent:
        raise HTTPException(status_code=404, detail="No device with notifications turned on. Turn them on first.")
    return {"message": f"Test notification sent to {sent} device{'s' * (sent != 1)}.", "devices": sent}
