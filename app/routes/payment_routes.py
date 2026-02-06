# app/routes/payment_routes.py

from fastapi import APIRouter, Depends, Query
from app.schemas.payment import CustomerPaymentRequest
from app.services.payment_service import (
    customer_payment,
    get_payments_by_customer,
)
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/payments", tags=["Payments"])


# -------------------------------------------------
# CUSTOMER PAYMENT (FIFO – SINGLE SOURCE OF TRUTH)
# -------------------------------------------------
@router.post("/customer")
async def customer_payment_route(
    data: CustomerPaymentRequest,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY")),
):
    return await customer_payment(
        customer_id=data.customer_id,
        amount=data.amount,
        current_user=current_user,
    )


# -------------------------------------------------
# GET PAYMENTS BY CUSTOMER (FIX FOR 404)
# -------------------------------------------------
@router.get("/")
async def payments_by_customer(
    customer_id: str = Query(...),
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY")),
):
    return await get_payments_by_customer(customer_id)
