from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(..., max_length=100)
    email: EmailStr = Field(..., max_length=100)
    password: str = Field(..., max_length=128)  # bcrypt ignores anything past 72 bytes anyway
    # Sign-up consent. Checked in the route (not here) so missing fields get a friendly message.
    age_group: str | None = Field(None, max_length=10)          # "under_13", "13_17" or "18_plus"
    accept_terms: bool = False            # agreed to the Terms and Privacy Policy
    guardian_consent: bool = False        # 13-17 only: a parent or guardian knows and agrees

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True