from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, EmailStr

from app.database import Role


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    role: Role

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BookCreate(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    author: str = Field(min_length=2, max_length=100)
    price: float = Field(gt=0)


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    price: float

    model_config = ConfigDict(from_attributes=True)


class BookUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    author: str = Field(min_length=2, max_length=100)
    price: float = Field(gt=0)


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    is_active: bool


class NotificationRecord(BaseModel):
    kind: str
    target: str
    event: str
    status: str
    attempts: int
    detail: str | None = None
    payload: dict[str, Any]
    finished_at: datetime
