from pydantic import BaseModel
from typing import Literal


class StockAdjustmentCreate(BaseModel):
    item_id: str
    quantity: int
    movement_type: Literal["IN", "OUT"]
    reason: str
