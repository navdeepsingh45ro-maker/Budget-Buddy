import logging
from sqlalchemy.orm import Session
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from models.recurring_transaction_model import RecurringTransaction
from models.recurring_transaction_model import RecurringTransaction
from services.expense_service import ExpenseService

logger = logging.getLogger("recurring_transaction_service")

VALID_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}


class RecurringTransactionService:
    """
    Manages recurring transaction templates and their lifecycle.
    Does NOT duplicate expense creation logic — it creates real Expense
    rows and then delegates to the same insight/trigger pipeline that
    manual expenses use.
    """

    # ── CRUD ──────────────────────────────────────────────────

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        title: str,
        amount: float,
        category: str,
        frequency: str,
        start_date: date,
        subcategory: str = None,
        notes: str = None,
        payment_method: str = None,
        end_date: date = None,
    ) -> RecurringTransaction:
        if frequency not in VALID_FREQUENCIES:
            raise ValueError(f"Invalid frequency: {frequency}")

        rt = RecurringTransaction(
            user_id=user_id,
            title=title,
            amount=amount,
            category=category,
            subcategory=subcategory,
            notes=notes,
            payment_method=payment_method,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            next_run=start_date,
        )
        db.add(rt)
        db.commit()
        db.refresh(rt)
        return rt

    @staticmethod
    def update(
        db: Session,
        user_id: int,
        rt_id: int,
        **kwargs,
    ) -> RecurringTransaction:
        rt = db.query(RecurringTransaction).filter(
            RecurringTransaction.id == rt_id,
            RecurringTransaction.user_id == user_id,
        ).first()
        if not rt:
            return None

        allowed = {
            "title", "amount", "category", "subcategory", "notes",
            "payment_method", "frequency", "start_date", "end_date", "is_active",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(rt, key, value)

        if "frequency" in kwargs or "start_date" in kwargs:
            # Recalculate next_run when schedule changes
            rt.next_run = rt.start_date

        db.commit()
        db.refresh(rt)
        return rt

    @staticmethod
    def delete(db: Session, user_id: int, rt_id: int) -> bool:
        rt = db.query(RecurringTransaction).filter(
            RecurringTransaction.id == rt_id,
            RecurringTransaction.user_id == user_id,
        ).first()
        if not rt:
            return False
        db.delete(rt)
        db.commit()
        return True

    @staticmethod
    def get_all(db: Session, user_id: int):
        return db.query(RecurringTransaction).filter(
            RecurringTransaction.user_id == user_id,
        ).order_by(RecurringTransaction.next_run.asc()).all()

    @staticmethod
    def get_by_id(db: Session, user_id: int, rt_id: int):
        return db.query(RecurringTransaction).filter(
            RecurringTransaction.id == rt_id,
            RecurringTransaction.user_id == user_id,
        ).first()

    # ── Scheduler core ────────────────────────────────────────

    @staticmethod
    def process_due_transactions(db: Session):
        """
        Called by the scheduler.  Finds all active templates whose
        next_run <= today, creates a real Expense for each, then
        advances next_run.  Deactivates templates past their end_date.
        
        Returns the list of (user_id, expense_id) pairs that were created.
        """
        today = date.today()
        created = []

        due = db.query(RecurringTransaction).filter(
            RecurringTransaction.is_active == True,
            RecurringTransaction.next_run <= today,
        ).all()

        for rt in due:
            # End-date guard
            if rt.end_date and today > rt.end_date:
                rt.is_active = False
                db.commit()
                continue

            # ── Create real Expense using ExpenseService ──
            expense = ExpenseService.process_new_expense(
                db=db,
                user_id=rt.user_id,
                amount=rt.amount,
                category=rt.category,
                subcategory=rt.subcategory,
                note=rt.notes,
                payment_method=rt.payment_method,
                expense_date=today,
                is_recurring=True,
                rt_title=rt.title
            )

            created.append((rt.user_id, expense.id))

            # Advance next_run
            rt.next_run = RecurringTransactionService._advance_date(
                rt.next_run, rt.frequency
            )

            # Auto-deactivate if the new next_run exceeds end_date
            if rt.end_date and rt.next_run > rt.end_date:
                rt.is_active = False

            db.commit()

        return created

    # ── Date arithmetic ───────────────────────────────────────

    @staticmethod
    def _advance_date(current: date, frequency: str) -> date:
        if frequency == "daily":
            return current + timedelta(days=1)
        elif frequency == "weekly":
            return current + timedelta(weeks=1)
        elif frequency == "monthly":
            return current + relativedelta(months=1)
        elif frequency == "yearly":
            return current + relativedelta(years=1)
        else:
            return current + timedelta(days=1)
