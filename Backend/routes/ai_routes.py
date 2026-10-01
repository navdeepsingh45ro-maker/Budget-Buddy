import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from services.gemini_parser import GeminiParser
from services.gemini_client import GeminiUnavailable
from services.receipt_scanner import scan_receipt
from services.gemini_chat import ChatLimitReached, ask_buddy
from services.monthly_report import (
    available_report_months, build_monthly_report, coach_tip_from_last_report,
    last_month_report_missing, pregenerate_report,
)
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
    message: str = Field(..., min_length=1, max_length=500)

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
    live (no AI call). The coaching tip comes from last month's report ideas
    (cached, no extra AI call); before a first report exists, it falls back to
    a situation tip that is refreshed only when the situation changes."""
    summary = FinancialSummaryGenerator.generate_summary(current_user.id, db)
    insight = build_insight(summary)

    ai_tip, ai_tip_source = None, None
    report_tip = coach_tip_from_last_report(db, current_user.id)
    if report_tip:
        ai_tip, ai_tip_source = report_tip["tip"], report_tip["source"]
    else:
        missing = last_month_report_missing(db, current_user.id)
        if missing:
            # Last month's report wasn't generated yet (e.g. server was off on the 1st).
            background_tasks.add_task(pregenerate_report, current_user.id, *missing)

        key = situation_key(summary, insight)
        record = db.query(AIInsight).filter(AIInsight.user_id == current_user.id).first()
        if record and record.summary_hash == key_hash(key):
            ai_tip = record.insight or None
        else:
            background_tasks.add_task(refresh_user_insight, current_user.id)

    return {
        "status": "ready",
        "insight": insight["insight"],
        "reminder": insight["reminder"],
        "severity": insight["severity"],
        "situation": insight["situation"],
        "ai_tip": ai_tip,
        "ai_tip_source": ai_tip_source,
        "last_updated": None,  # computed live, so there is no "x hours ago"
    }


@router.get("/report-months")
def get_report_months(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Months with expenses for the report picker; default is last month."""
    return available_report_months(db, current_user.id)


@router.post("/chat")
def chat_with_buddy(request: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return {"reply": ask_buddy(db, current_user.id, request.message.strip())}
    except ChatLimitReached:
        raise HTTPException(status_code=429, detail="You've reached today's limit for Buddy chats. Try again tomorrow.")
    except GeminiUnavailable:
        logger.exception("Chat failed")
        raise HTTPException(status_code=503, detail=AI_BUSY)


@router.get("/monthly-report")
def get_monthly_report(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Always succeeds: the facts are computed by code; only the commentary uses AI (cached).
    return build_monthly_report(db, current_user.id, month, year)
