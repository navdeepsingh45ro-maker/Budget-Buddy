from auth.auth2 import get_current_user
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, Field
from schemas.user_schema import UserCreate, UserResponse
from models.user_model import User
from database import SessionLocal
from auth.hashing import hash_password
from schemas.login_schema import LoginSchema
from auth.hashing import verify_password
from auth.jwt_handler import token_for_user
from sqlalchemy.orm import Session
from database import get_db
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Request
from fastapi.responses import JSONResponse
from models.user_settings_model import UserSettings
from models.user_consent_model import UserConsent
from services.rate_limit import Limit, client_ip
from services import email_verification
from sqlalchemy import func

# Brute-force protection. Failed logins are counted per account and per IP address.
LOGIN_PER_EMAIL = Limit("login-email", max_events=10, window_seconds=15 * 60,
                        message="Too many failed logins. Please try again in {wait}, or reset your password.")
LOGIN_PER_IP = Limit("login-ip", max_events=50, window_seconds=15 * 60)
SIGNUP_PER_IP = Limit("signup-ip", max_events=10, window_seconds=60 * 60,
                      message="Too many accounts created from this network. Please try again in {wait}.")
PASSWORD_CHECK_PER_USER = Limit("password-check", max_events=10, window_seconds=15 * 60)

# Verified when the email doesn't exist, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = hash_password("not-a-real-password")


def find_user_by_email(db: Session, email: str) -> User | None:
    """Emails are matched ignoring case and surrounding spaces."""
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()

router = APIRouter()
@router.post("/users/")
def create_user(user: UserCreate, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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
    SIGNUP_PER_IP.use(client_ip(request))
    email = user.email.strip().lower()
    _purge_stale_unverified(db)
    if find_user_by_email(db, email):
        # Same answer whether that account is verified or still waiting: an unverified
        # sign-up is never overwritten, so nobody can slip their password onto it.
        raise HTTPException(status_code=400, detail="An account with this email already exists. Try logging in.")

    hashed_password = hash_password(user.password)
    new_user = User(name=user.name.strip(), email=email, password=hashed_password)
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
    
    email_verification.start(db, new_user)
    needs_code = not email_verification.is_verified(db, new_user)
    if needs_code:
        email_verification.send_code(db, new_user, background_tasks)
    return {"message": "User created successfully", "verification_required": needs_code, "email": email}

@router.post("/login")
def login(request: LoginSchema, http_request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email, ip = request.email.strip().lower(), client_ip(http_request)
    LOGIN_PER_EMAIL.check(email)
    LOGIN_PER_IP.check(ip)

    user = find_user_by_email(db, email)
    # Always run one bcrypt check so the response time doesn't reveal whether the email exists.
    password_ok = verify_password(request.password, user.password if user else _DUMMY_HASH)

    if not user or not password_ok:
        LOGIN_PER_EMAIL.hit(email)
        LOGIN_PER_IP.hit(ip)
        raise HTTPException(
        status_code=401,
        detail="Invalid email or password")
    LOGIN_PER_EMAIL.reset(email)
    if not email_verification.is_verified(db, user):
        # Right password, but the email was never confirmed: send a fresh code and ask for it.
        # (Returned, not raised: background tasks, i.e. the email, only run on a returned response.)
        email_verification.send_code(db, user, background_tasks)
        return JSONResponse(status_code=403, background=background_tasks,
                            content={"detail": "Please verify your email first. We've sent you a new code."})
    access_token = token_for_user(user)

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
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., max_length=128)


class DeleteAccount(BaseModel):
    password: str = Field(..., max_length=128)


class UpdateSettings(BaseModel):
    carry_over_budget: bool | None = None
    onboarding_completed: bool | None = None


def _check_password(user: User, password: str, wrong_message: str) -> None:
    """Confirm the account password, limiting guesses in case a session was stolen."""
    PASSWORD_CHECK_PER_USER.check(user.id)
    if not verify_password(password, user.password):
        PASSWORD_CHECK_PER_USER.hit(user.id)
        raise HTTPException(status_code=400, detail=wrong_message)
    PASSWORD_CHECK_PER_USER.reset(user.id)


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
    _check_password(current_user, body.current_password, "Your current password is incorrect")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if verify_password(body.new_password, current_user.password):
        raise HTTPException(status_code=400, detail="Your new password must be different from the current one")
    current_user.password = hash_password(body.new_password)
    db.commit()
    # Changing the password signs out every other device; this device gets a fresh token.
    return {"message": "Password changed", "access_token": token_for_user(current_user), "token_type": "bearer"}


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
    _check_password(current_user, body.password, "Password is incorrect")
    _delete_user(db, current_user.id)
    return {"message": "Your account and all your data have been deleted"}


def _delete_user(db: Session, user_id: int) -> None:
    for model in USER_OWNED_MODELS:
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


def _purge_stale_unverified(db: Session) -> None:
    """Remove sign-ups whose email was never confirmed, so the address is free again."""
    for user_id in email_verification.stale_unverified_user_ids(db):
        _delete_user(db, user_id)


def _user_owned_models():
    from models.ai_insight_model import AIInsight
    from models.ai_report_model import AIReport
    from models.budget_model import Budget
    from models.device_model import Device
    from models.email_verification_model import EmailVerification
    from models.expense_model import Expense
    from models.notification_model import Notification
    from models.notification_preferences_model import NotificationPreferences
    from models.password_reset_model import PasswordReset
    from models.push_subscription_model import PushSubscription
    from models.recurring_transaction_model import RecurringTransaction
    return [Expense, Budget, RecurringTransaction, Notification, NotificationPreferences, Device,
            PushSubscription, AIInsight, AIReport, PasswordReset, UserSettings, UserConsent, EmailVerification]


USER_OWNED_MODELS = _user_owned_models()
