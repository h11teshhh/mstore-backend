from pydantic import BaseModel
from typing import Optional


class CompletePaymentRequest(BaseModel):
    order_id: str
    customer_id: str


class PartialPaymentRequest(BaseModel):
    order_id: str
    customer_id: str
    amount: float


class CustomerPaymentRequest(BaseModel):
    customer_id: str
    amount: float
