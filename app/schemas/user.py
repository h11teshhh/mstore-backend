from pydantic import BaseModel
from typing import Literal
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


class UserLogin(BaseModel):
    mobile: str
    password: str
