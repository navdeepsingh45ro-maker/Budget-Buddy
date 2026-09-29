from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user_model import User
from models.notification_preferences_model import NotificationPreferences
from auth.auth2 import get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/notification-preferences", tags=["Notification Preferences"])

class PreferencesUpdate(BaseModel):
    notify_ai: Optional[bool] = None
    notify_budget: Optional[bool] = None
    notify_reminders: Optional[bool] = None
    notify_weekly: Optional[bool] = None
    notify_monthly: Optional[bool] = None
    notify_system: Optional[bool] = None
    future_notify_bills: Optional[bool] = None
    future_notify_goals: Optional[bool] = None
    future_notify_savings: Optional[bool] = None

@router.get("/")
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == current_user.id).first()
    if not prefs:
        # Fallback to create defaults if somehow missing
        prefs = NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
        
    return prefs

@router.put("/")
def update_preferences(
    prefs_data: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == current_user.id).first()
    if not prefs:
        raise HTTPException(status_code=404, detail="Preferences not found")
        
    update_data = prefs_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prefs, key, value)
        
    db.commit()
    db.refresh(prefs)
    return prefs
