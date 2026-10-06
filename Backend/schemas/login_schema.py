from pydantic import BaseModel, Field

class LoginSchema(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)