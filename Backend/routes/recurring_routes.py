from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.user_model import User
from auth.auth2 import get_current_user
from services.recurring_transaction_service import RecurringTransactionService
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

router = APIRouter(prefix="/recurring", tags=["Recurring Transactions"])


class RecurringCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    amount: float = Field(..., gt=0)
    category: str
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    frequency: str = Field(..., description="daily | weekly | monthly | yearly")
    start_date: date
    end_date: Optional[date] = None


class RecurringUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


@router.post("/")
def create_recurring(
    data: RecurringCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        rt = RecurringTransactionService.create(
            db=db,
            user_id=current_user.id,
            title=data.title,
            amount=data.amount,
            category=data.category,
            subcategory=data.subcategory,
            notes=data.notes,
            payment_method=data.payment_method,
            frequency=data.frequency,
            start_date=data.start_date,
            end_date=data.end_date,
        )
        return {"message": "Recurring transaction created", "id": rt.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
def get_all_recurring(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = RecurringTransactionService.get_all(db, current_user.id)
    return {"recurring_transactions": items}


@router.get("/{rt_id}")
def get_recurring(
    rt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rt = RecurringTransactionService.get_by_id(db, current_user.id, rt_id)
    if not rt:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    return rt


@router.put("/{rt_id}")
def update_recurring(
    rt_id: int,
    data: RecurringUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = data.dict(exclude_unset=True)
    rt = RecurringTransactionService.update(db, current_user.id, rt_id, **update_data)
    if not rt:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    return {"message": "Recurring transaction updated"}


@router.delete("/{rt_id}")
def delete_recurring(
    rt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = RecurringTransactionService.delete(db, current_user.id, rt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    return {"message": "Recurring transaction deleted"}
