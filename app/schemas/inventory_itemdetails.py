from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class InventoryItemDetailCreate(BaseModel):
    item_id: str
    quantity: int = Field(..., gt=0)
    movement_type: Literal["IN", "OUT"]


class InventoryItemDetailResponse(BaseModel):
    id: str
    item_id: str
    quantity: int
    movement_type: str
    created_by: str
    created_at: datetime
    updated_at: datetime
