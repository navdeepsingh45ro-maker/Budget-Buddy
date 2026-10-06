"""Registers every model on Base.metadata.

THE one place to add a new model: import it here. Alembic (alembic/env.py) and
the app (main.py via migrations_runner) both import this package, so a model
listed here is seen by `alembic revision --autogenerate` and by the tests that
check the migrations match the models.
"""
from models.ai_insight_model import AIInsight  # noqa: F401
from models.ai_report_model import AIReport  # noqa: F401
from models.budget_model import Budget  # noqa: F401
from models.device_model import Device  # noqa: F401
from models.email_verification_model import EmailVerification  # noqa: F401
from models.expense_model import Expense  # noqa: F401
from models.notification_model import Notification  # noqa: F401
from models.notification_preferences_model import NotificationPreferences  # noqa: F401
from models.password_reset_model import PasswordReset  # noqa: F401
from models.push_subscription_model import PushSubscription  # noqa: F401
from models.recurring_transaction_model import RecurringTransaction  # noqa: F401
from models.user_consent_model import UserConsent  # noqa: F401
from models.user_model import User  # noqa: F401
from models.user_settings_model import UserSettings  # noqa: F401
