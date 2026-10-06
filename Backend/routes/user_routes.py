from auth.auth2 import get_current_user
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from schemas.user_schema import UserCreate, UserResponse
from models.user_model import User
from database import SessionLocal
from auth.hashing import hash_password
from schemas.login_schema import LoginSchema
from auth.hashing import verify_password
from auth.jwt_handler import create_access_token
from sqlalchemy.orm import Session
from database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Request
from models.user_settings_model import UserSettings
from models.user_consent_model import UserConsent

router = APIRouter()
@router.post("/users/")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Age and consent come first: an under-13 attempt is refused before anything is read or stored.
    if user.age_group not in AGE_GROUPS:
        raise HTTPException(status_code=400, detail="Please tell us your age group")
    if user.age_group == "under_13":
        raise HTTPException(status_code=403, detail="Sorry, you need to be 13 or older to use Budget Buddy.")
    if user.age_group == "13_17" and not user.guardian_consent:
        raise HTTPException(status_code=400, detail="If you're under 18, a parent or guardian needs to agree before you sign up")
    if not user.accept_terms:
        raise HTTPException(status_code=400, detail="Please agree to the Terms of Service and Privacy Policy")
    if not user.name.strip():
        raise HTTPException(status_code=400, detail="Please enter your name")
    if len(user.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    hashed_password = hash_password(user.password)
    new_user = User(name=user.name, email=user.email, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # New accounts see the welcome tutorial once (existing accounts have no settings row).
    db.add(UserSettings(user_id=new_user.id, carry_over_budget=True, onboarding_completed_at=None))
    now = datetime.utcnow()
    db.add(UserConsent(user_id=new_user.id, age_group=user.age_group, terms_version=TERMS_VERSION,
                       terms_accepted_at=now, guardian_consent_at=now if user.age_group == "13_17" else None))

    # Create default notification preferences
    from models.notification_preferences_model import NotificationPreferences
    default_prefs = NotificationPreferences(user_id=new_user.id)
    db.add(default_prefs)
    db.commit()
    
    from services.notification_service import NotificationService
    
    if default_prefs.notify_system:
        NotificationService.create_system_notification(
            db=db,
            user_id=new_user.id,
            title="Welcome to BudgetBuddy!",
            message="Start tracking your expenses and let Buddy help you manage your money.",
            icon="waving_hand"
        )
    
    return {"message": "User created successfully"}

@router.post("/login")
def login(request: LoginSchema, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == request.email).first()

    password_ok = verify_password(request.password,user.password) if user else False

    if not user or not password_ok:
        raise HTTPException(
        status_code=401,
        detail="Invalid username or password")
    access_token = create_access_token(data={"user_id": user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/users/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user 


# ── Account & settings ─────────────────────────────────────────

MIN_PASSWORD_LENGTH = 8
AGE_GROUPS = ("under_13", "13_17", "18_plus")
TERMS_VERSION = "2026-10-01"  # bump with the "Last updated" date on terms.html / privacy.html


class UpdateProfile(BaseModel):
    name: str = Field(..., max_length=100)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str


class DeleteAccount(BaseModel):
    password: str


class UpdateSettings(BaseModel):
    carry_over_budget: bool | None = None
    onboarding_completed: bool | None = None


def _settings_row(db: Session, user_id: int) -> UserSettings | None:
    return db.query(UserSettings).filter(UserSettings.user_id == user_id).first()


@router.put("/users/me", response_model=UserResponse)
def update_profile(body: UpdateProfile, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Please enter your name")
    current_user.name = name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/users/me/password")
def change_password(body: ChangePassword, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Your current password is incorrect")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if verify_password(body.new_password, current_user.password):
        raise HTTPException(status_code=400, detail="Your new password must be different from the current one")
    current_user.password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed"}


@router.get("/users/me/settings")
def get_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _settings_row(db, current_user.id)
    return {
        "carry_over_budget": True if row is None else bool(row.carry_over_budget),
        # No row = account created before the tutorial existed: don't force it on them.
        "onboarding_completed": row is None or row.onboarding_completed_at is not None,
    }


@router.put("/users/me/settings")
def update_settings(body: UpdateSettings, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _settings_row(db, current_user.id)
    if row is None:
        row = UserSettings(user_id=current_user.id, carry_over_budget=True, onboarding_completed_at=datetime.utcnow())
        db.add(row)
    if body.carry_over_budget is not None:
        row.carry_over_budget = body.carry_over_budget
    if body.onboarding_completed is not None:
        row.onboarding_completed_at = datetime.utcnow() if body.onboarding_completed else None
    db.commit()
    return get_settings(current_user, db)


@router.post("/users/me/delete")
def delete_account(body: DeleteAccount, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete the account and every row that belongs to it."""
    if not verify_password(body.password, current_user.password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    user_id = current_user.id
    for model in USER_OWNED_MODELS:
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()
    return {"message": "Your account and all your data have been deleted"}


def _user_owned_models():
    from models.ai_insight_model import AIInsight
    from models.ai_report_model import AIReport
    from models.budget_model import Budget
    from models.device_model import Device
    from models.expense_model import Expense
    from models.notification_model import Notification
    from models.notification_preferences_model import NotificationPreferences
    from models.password_reset_model import PasswordReset
    from models.push_subscription_model import PushSubscription
    from models.recurring_transaction_model import RecurringTransaction
    return [Expense, Budget, RecurringTransaction, Notification, NotificationPreferences, Device,
            PushSubscription, AIInsight, AIReport, PasswordReset, UserSettings, UserConsent]


USER_OWNED_MODELS = _user_owned_models()
