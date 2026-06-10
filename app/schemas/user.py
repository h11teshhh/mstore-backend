from pydantic import BaseModel
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    DELIVERY = "DELIVERY"


class UserCreate(BaseModel):
    name: str
    mobile: str
    password: str
    address: str
    role: UserRole
    email: Optional[str] = None   # Optional — not required for login or forgot-password


class UserLogin(BaseModel):
    mobile: str
    password: str
