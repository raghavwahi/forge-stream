import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserInDB(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    avatar_url: str | None = None
    password_hash: str | None = None
    provider: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password_hash: str
    provider: str = "email"
