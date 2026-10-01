import logging
from sqlalchemy.orm import Session
from datetime import date
from models.expense_model import Expense
from services.subcategory_rules import detect_subcategory
from services.insight_updater import refresh_user_insight
from services.trigger_service import evaluate_budget_triggers
from services.notification_service import NotificationService
from services.push_service import USER_SETUP

logger = logging.getLogger("expense_service")

class ExpenseService:
    @staticmethod
    def process_new_expense(
        db: Session,
        user_id: int,
        amount: float,
        category: str,
        subcategory: str = None,
        note: str = None,
        payment_method: str = None,
        expense_date: date = None,
        is_recurring: bool = False,
        rt_title: str = None,
        background_tasks = None
    ) -> Expense:
        """
        Single source of truth for creating a new expense.
        Handles subcategory detection, DB insertion, and triggers the post-creation pipeline.
        """
        # 1. Subcategory (merchant/app/person) from the note, by rules: instant, no API call
        if not subcategory and note:
            subcategory = detect_subcategory(note)

        # 2. Database Insertion
        expense = Expense(
            amount=amount,
            category=category,
            subcategory=subcategory,
            note=note,
            payment_method=payment_method,
            expense_date=expense_date,
            user_id=user_id
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)

        # 3. Post-Creation Pipeline
        ExpenseService._post_creation_pipeline(db, user_id, expense, is_recurring, rt_title, background_tasks)

        return expense

    @staticmethod
    def _post_creation_pipeline(db: Session, user_id: int, expense: Expense, is_recurring: bool, rt_title: str = None, background_tasks = None):
        """
        Centralized pipeline for all downstream behavior after an expense is created.
        """
        # A. Trigger Notifications for Recurring Expenses
        if is_recurring:
            title = "Recurring Expense Added"
            msg_target = rt_title if rt_title else (expense.note or expense.category)
            message = f"Your recurring expense for {msg_target} (₹{expense.amount}) was automatically added."
            try:
                NotificationService.create_notification(
                    db=db,
                    user_id=user_id,
                    title=title,
                    message=message,
                    category="system",
                    source="scheduler",
                    icon="event_repeat",
                    priority="info",
                    push_origin=USER_SETUP,
                )
            except Exception as e:
                logger.error(f"Failed to create recurring notification for user {user_id}: {e}")

        # B. AI Insights & Budget Evaluation
        # Budget alerts caused by a recurring bill reach the user's devices;
        # ones caused by an expense they just added in the app stay in the drawer.
        budget_push = USER_SETUP if is_recurring else None
        if background_tasks:
            background_tasks.add_task(refresh_user_insight, user_id)
            background_tasks.add_task(evaluate_budget_triggers, user_id, budget_push)
        else:
            try:
                refresh_user_insight(user_id)
            except Exception as e:
                logger.error(f"Insight refresh failed for user {user_id}: {e}")

            try:
                evaluate_budget_triggers(user_id, budget_push)
            except Exception as e:
                logger.error(f"Budget trigger failed for user {user_id}: {e}")
