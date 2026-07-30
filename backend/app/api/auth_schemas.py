from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from pydantic import ConfigDict
class RegisterRequest(BaseModel):
    user_name: str = Field(..., min_length=3, max_length=50)
    email:EmailStr
    password:str=Field(
        ...,
        min_length=8,
        max_length=128,
    )



class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_name: str = Field(..., min_length=3, max_length=50)
    email:EmailStr
    created_at:datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"