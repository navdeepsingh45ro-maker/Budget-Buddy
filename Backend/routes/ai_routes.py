import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from services.gemini_parser import GeminiParser
from services.gemini_client import GeminiUnavailable
from services.receipt_scanner import scan_receipt
from models.ai_insight_model import AIInsight
from models.user_model import User
from auth.auth2 import get_current_user
from database import get_db
from services.summary_service import FinancialSummaryGenerator
from services.insight_engine import build_insight
from services.insight_updater import key_hash, refresh_user_insight, situation_key

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger("ai_routes")


class ParseExpenseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Natural language expense text")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)

AI_BUSY = "Buddy's AI is busy right now. Please try again in a moment or enter the expense manually."

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("/parse-expense")
def parse_expense(request: ParseExpenseRequest, current_user: User = Depends(get_current_user)):
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        return GeminiParser().parse_expense(text)
    except GeminiUnavailable:
        logger.exception("Voice parsing failed")
        raise HTTPException(status_code=503, detail=AI_BUSY)


@router.post("/scan-receipt")
async def scan_receipt_route(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    if file.content_type not in RECEIPT_TYPES:
        raise HTTPException(status_code=400, detail="Please upload a photo (JPG, PNG, WEBP or HEIC).")

    image = await file.read(MAX_RECEIPT_BYTES + 1)
    if not image:
        raise HTTPException(status_code=400, detail="The photo is empty. Please try again.")
    if len(image) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=413, detail="That photo is too large (max 10 MB).")

    try:
        result = await run_in_threadpool(scan_receipt, image, file.content_type)
    except GeminiUnavailable:
        logger.exception("Receipt scan failed")
        raise HTTPException(status_code=503, detail=AI_BUSY)

    if not result["is_receipt"] or result["amount"] is None:
        raise HTTPException(
            status_code=422,
            detail="Couldn't read a total from that photo. Try again with the whole receipt in frame and good light.",
        )
    return result


@router.get("/insight")
def get_insight(background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Coach Insight card. Numbers and main message are rule-based and computed
    live (no AI call). The optional AI tip is shown only if it was written for
    the user's current situation; otherwise a refresh is queued in the background."""
    summary = FinancialSummaryGenerator.generate_summary(current_user.id, db)
    insight = build_insight(summary)
    key = situation_key(summary, insight)

    record = db.query(AIInsight).filter(AIInsight.user_id == current_user.id).first()
    tip_is_current = bool(record and record.summary_hash == key_hash(key))
    if not tip_is_current:
        background_tasks.add_task(refresh_user_insight, current_user.id)

    return {
        "status": "ready",
        "insight": insight["insight"],
        "reminder": insight["reminder"],
        "severity": insight["severity"],
        "situation": insight["situation"],
        "ai_tip": (record.insight or None) if tip_is_current else None,
        "last_updated": None,  # computed live, so there is no "x hours ago"
    }

@router.post("/chat")
def chat_with_buddy(request: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from services.gemini_chat import GeminiChat
    from services.summary_service import FinancialSummaryGenerator
    
    summary = FinancialSummaryGenerator.generate_summary(current_user.id, db)
    chat = GeminiChat()
    response = chat.ask(request.message, summary)
    return {"reply": response}

@router.get("/monthly-report")
def get_monthly_report(month: int, year: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from services.gemini_chat import GeminiChat
    from sqlalchemy import extract
    from models.expense_model import Expense
    
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        extract('month', Expense.expense_date) == month,
        extract('year', Expense.expense_date) == year
    ).all()
    
    chat = GeminiChat()
    report = chat.generate_monthly_report(expenses, month, year)
    return {"report": report}
