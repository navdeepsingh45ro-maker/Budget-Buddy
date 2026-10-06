from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    # Sign-up consent. Checked in the route (not here) so missing fields get a friendly message.
    age_group: str | None = None          # "under_13", "13_17" or "18_plus"
    accept_terms: bool = False            # agreed to the Terms and Privacy Policy
    guardian_consent: bool = False        # 13-17 only: a parent or guardian knows and agrees

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True