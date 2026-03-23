from pydantic import BaseModel, EmailStr
from uuid import UUID


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    tenant_slug: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    tenant_id: UUID
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: str
