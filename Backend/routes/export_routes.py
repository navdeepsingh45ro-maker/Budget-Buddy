from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from database import get_db
from models.user_model import User
from auth.auth2 import get_current_user
from services.export.export_service import ExportService

router = APIRouter()

def _handle_export(
    format_type: str,
    search: Optional[str],
    category: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    min_amount: Optional[float],
    max_amount: Optional[float],
    sort: Optional[str],
    current_user: User,
    db: Session
):
    try:
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None

        file_bytes, mime_type, filename = ExportService.generate_export(
            db=db,
            user_id=current_user.id,
            format_type=format_type,
            search=search,
            category=category,
            start_date=parsed_start,
            end_date=parsed_end,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort
        )

        return Response(
            content=file_bytes,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export generation failed: {str(e)}")

@router.get("/csv")
def export_csv(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort: Optional[str] = "newest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _handle_export("csv", search, category, start_date, end_date, min_amount, max_amount, sort, current_user, db)

@router.get("/excel")
def export_excel(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort: Optional[str] = "newest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _handle_export("excel", search, category, start_date, end_date, min_amount, max_amount, sort, current_user, db)

@router.get("/pdf")
def export_pdf(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    sort: Optional[str] = "newest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _handle_export("pdf", search, category, start_date, end_date, min_amount, max_amount, sort, current_user, db)
