from pydantic import BaseModel, Field   
class BudgetCreate(BaseModel):
    monthly_budget: float = Field(..., gt=0, description="Monthly budget amount")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    year: int = Field(..., ge=2000, le=2100, description="Year (2000-2100)")

class BudgetResponse(BaseModel):
    id: int
    month: int
    year: int
    user_id: int

    class Config:
        orm_mode = True