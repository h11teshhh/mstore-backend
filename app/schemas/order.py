from pydantic import BaseModel
from typing import List


class OrderItemCreate(BaseModel):
    item_id: str
    quantity: int


class OrderCreate(BaseModel):
    customer_id: str
    items: List[OrderItemCreate]