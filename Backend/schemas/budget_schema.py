from pydantic import BaseModel, Field   
class BudgetCreate(BaseModel):
    monthly_budget: float = Field(
        ...,
        gt=0,
        le=1_000_000_000,
        allow_inf_nan=False,
        description="Monthly budget amount"
    )

class BudgetResponse(BaseModel):
    id: int
    month: int
    year: int
    user_id: int

    class Config:
        from_attributes = True

class BudgetDetailResponse(BudgetResponse):
    monthly_budget: float