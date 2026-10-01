from sqlalchemy.orm import Session, Query
from sqlalchemy import or_, asc, desc, func
from models.expense_model import Expense
from datetime import date
from typing import Optional


class ExpenseQueryService:
    """
    Reusable Expense Query Engine.
    Dynamically builds SQLAlchemy queries based on supplied filters.
    
    Consumed by:
      - Expense History
      - Budget History
      - Export System
      - Future Reports
      - Future AI Queries
    """

    @staticmethod
    def query(
        db: Session,
        user_id: int,
        search: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        sort: Optional[str] = "newest",
        page: int = 1,
        limit: int = 20,
        skip_pagination: bool = False
    ) -> dict:
        """
        Build and execute a filtered, sorted, paginated expense query.
        
        Returns:
            {
                "expenses": [...],
                "total": int,
                "page": int,
                "limit": int,
                "total_pages": int
            }
        """
        # Base query scoped to user
        q: Query = db.query(Expense).filter(Expense.user_id == user_id)

        # --- Search (merchant/title via note, payment method, or category name) ---
        if search:
            search_term = f"%{search}%"
            q = q.filter(
                or_(
                    Expense.note.ilike(search_term),
                    Expense.payment_method.ilike(search_term),
                    Expense.category.ilike(search_term),
                    Expense.subcategory.ilike(search_term)
                )
            )

        # --- Filter: Category ---
        if category:
            q = q.filter(Expense.category == category)

        # --- Filter: Date Range ---
        # Use expense_date if available, fallback to created_at
        if start_date:
            q = q.filter(
                or_(
                    Expense.expense_date >= start_date,
                    (Expense.expense_date == None) & (Expense.created_at >= start_date)  # noqa: E711
                )
            )
        if end_date:
            q = q.filter(
                or_(
                    Expense.expense_date <= end_date,
                    (Expense.expense_date == None) & (Expense.created_at <= end_date)  # noqa: E711
                )
            )

        # --- Filter: Amount Range ---
        if min_amount is not None:
            q = q.filter(Expense.amount >= min_amount)
        if max_amount is not None:
            q = q.filter(Expense.amount <= max_amount)

        # --- Sorting ---
        effective_date = func.coalesce(Expense.expense_date, func.date(Expense.created_at))
        sort_map = {
            "newest": (desc(effective_date), desc(Expense.created_at)),
            "oldest": (asc(effective_date), asc(Expense.created_at)),
            "highest": desc(Expense.amount),
            "lowest": asc(Expense.amount)
        }
        order = sort_map.get(sort, sort_map["newest"])
        q = q.order_by(*order) if isinstance(order, tuple) else q.order_by(order)

        # --- Pagination ---
        total = q.count()
        total_pages = max((total + limit - 1) // limit, 1)
        
        if skip_pagination:
            expenses = q.all()
            page = 1
            limit = total
        else:
            page = max(1, min(page, total_pages))
            offset = (page - 1) * limit
            expenses = q.offset(offset).limit(limit).all()

        return {
            "expenses": expenses,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }
