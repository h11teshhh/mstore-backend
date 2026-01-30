from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from typing import Optional


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=2)
    mobile: str = Field(..., min_length=10, max_length=10)
    area: str


class CustomerUpdate(BaseModel):
    name: Optional[str]
    mobile: Optional[str]
    area: Optional[str]
    is_active: Optional[bool]


class CustomerResponse(BaseModel):
    id: str
    role: str
    name: str
    mobile: str
    area: str
    current_due: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
