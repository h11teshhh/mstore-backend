from pydantic import BaseModel, Field
from typing import Optional


class InventoryCreate(BaseModel):
    item_name: str = Field(..., min_length=1)
    price: float


class InventoryResponse(BaseModel):
    id: str
    item_name: str
    price: float
    current_stock: int
    is_active: bool
