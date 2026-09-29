from fastapi import APIRouter, HTTPException, Depends
import json
import hashlib
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from services.gemini_parser import GeminiParser
from models.ai_insight_model import AIInsight
from models.user_model import User
from auth.auth2 import get_current_user
from database import get_db
from services.summary_service import FinancialSummaryGenerator

router = APIRouter(prefix="/ai", tags=["AI"])


class ParseExpenseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Natural language expense text")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)

@router.post("/parse-expense")
def parse_expense(request: ParseExpenseRequest, current_user: User = Depends(get_current_user)):
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        parser = GeminiParser()
        result = parser.parse_expense(text)
        return result

    except ValueError as e:
        # Missing API key or config issues
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        # Gemini API failures, network errors, etc.
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {str(e)}")

@router.get("/insight")
def get_insight(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    insight = db.query(AIInsight).filter(AIInsight.user_id == current_user.id).first()
    
    if insight:
        summary = FinancialSummaryGenerator.generate_summary(current_user.id, db)
        summary_str = json.dumps(summary, sort_keys=True)
        current_hash = hashlib.sha256(summary_str.encode('utf-8')).hexdigest()
        
        status = "ready" if current_hash == insight.summary_hash else "generating"
        
        return {
            "status": status,
            "insight": insight.insight,
            "reminder": insight.reminder,
            "last_updated": insight.updated_at.isoformat() if insight.updated_at else None
        }
    
    # Fallback if no insight generated yet
    return {
        "status": "fallback",
        "insight": "Log your first expense or set a budget to start getting insights.",
        "reminder": "Use the Add Expense button.",
        "last_updated": None
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
