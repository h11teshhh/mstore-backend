from pydantic import BaseModel
from typing import Literal


class UserCreate(BaseModel):
    name: str
    mobile: str
    password: str
    address: str
    role: Literal["admin", "delivery"]  # superadmin NOT allowed here


class UserLogin(BaseModel):
    mobile: str
    password: str
