from pydantic import BaseModel, Field   
class BudgetCreate(BaseModel):
    monthly_budget: float = Field(
        ...,
        gt=0,
        description="Monthly budget amount"
    )

class BudgetResponse(BaseModel):
    id: int
    month: int
    year: int
    user_id: int

    class Config:
        orm_mode = True

class BudgetDetailResponse(BudgetResponse):
    monthly_budget: float