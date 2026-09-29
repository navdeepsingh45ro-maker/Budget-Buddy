import logging
import threading
import time
from datetime import datetime
from database import SessionLocal
from services.recurring_transaction_service import RecurringTransactionService

logger = logging.getLogger("recurring_scheduler")

_scheduler_thread = None
_scheduler_running = False

# How often the scheduler checks for due transactions (in seconds)
CHECK_INTERVAL = 60 * 60  # every hour


def _scheduler_loop():
    """
    Background thread that periodically processes due recurring transactions.
    After creating expenses, it fires the same pipeline (insight + budget triggers)
    that manual expense creation uses — so dashboard, analytics, and notifications
    all update automatically with zero duplicate logic.
    """
    global _scheduler_running
    logger.info("Recurring transaction scheduler started.")

    while _scheduler_running:
        db = SessionLocal()
        try:
            created = RecurringTransactionService.process_due_transactions(db)

            # Pipeline (AI, Notifications, Budget) is now handled automatically 
            # inside ExpenseService.process_new_expense which is called by process_due_transactions.
            for user_id, expense_id in created:
                logger.info(f"Recurring expense created: expense_id={expense_id} for user_id={user_id}")

        except Exception as e:
            logger.error(f"Scheduler cycle failed: {e}")
        finally:
            db.close()

        time.sleep(CHECK_INTERVAL)

    logger.info("Recurring transaction scheduler stopped.")


def start_scheduler():
    """Call once at app startup (e.g. from main.py or a lifespan event)."""
    global _scheduler_thread, _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()


def stop_scheduler():
    """Gracefully stop the scheduler thread."""
    global _scheduler_running
    _scheduler_running = False
