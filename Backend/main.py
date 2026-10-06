import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import engine, Base  # noqa: F401
from migrations_runner import run_migrations
from models.user_model import User
from routes.user_routes import router
from models.expense_model import Expense
from routes.expense_routes import router as expense_router
from routes.budget_routes import router as budget_router
from routes.ai_routes import router as ai_router
from models.ai_insight_model import AIInsight
from models.notification_model import Notification
from models.device_model import Device
from models.notification_preferences_model import NotificationPreferences
from models.recurring_transaction_model import RecurringTransaction
from routes.notification_routes import router as notification_router
from routes.device_routes import router as device_router
from routes.notification_preferences_routes import router as preferences_router
from routes.recurring_routes import router as recurring_router
from routes.export_routes import router as export_router
from routes.auth_routes import router as auth_router
from models.password_reset_model import PasswordReset
from models.ai_report_model import AIReport
from models.push_subscription_model import PushSubscription
from models.user_consent_model import UserConsent
from models.email_verification_model import EmailVerification
from routes.push_routes import router as push_router
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the recurring transaction scheduler
    from services.recurring_scheduler import start_scheduler
    start_scheduler()
    yield

# APP_ENV=production hides the interactive API docs and drops the localhost CORS origins.
IS_PRODUCTION = os.getenv("APP_ENV", "").lower() == "production"

app = FastAPI(lifespan=lifespan, **({"docs_url": None, "redoc_url": None, "openapi_url": None} if IS_PRODUCTION else {}))


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Responses hold personal finance data: browsers and proxies must not keep copies.
    response.headers.setdefault("Cache-Control", "no-store")
    if IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

app.include_router(router)
app.include_router(auth_router)
app.include_router(push_router)
app.include_router(expense_router)
app.include_router(budget_router)
app.include_router(ai_router)
app.include_router(notification_router)
app.include_router(device_router)
app.include_router(preferences_router)
app.include_router(recurring_router)
app.include_router(export_router, prefix="/export")

run_migrations()  # create/upgrade tables (see migrations_runner.py) before the scheduler starts

# start_scheduler() handled in lifespan

@app.get("/")
def home():
   return {"message": "Expense Tracker API is running!"} 

LOCAL_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
]
# Deployed frontend URL(s), comma-separated, e.g. "https://budgetbuddy.netlify.app"
EXTRA_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=([] if IS_PRODUCTION else LOCAL_ORIGINS) + EXTRA_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
