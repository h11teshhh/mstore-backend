from fastapi import APIRouter, Depends, Query
from app.schemas.payment import CompletePaymentRequest, PartialPaymentRequest
from app.services.payment_service import (
    complete_payment,
    partial_payment,
    get_payments_by_customer
)
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/complete")
async def pay_complete(
    data: CompletePaymentRequest,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY"))
):
    return await complete_payment(
        data.order_id,
        data.customer_id
    )


@router.post("/partial")
async def pay_partial(
    data: PartialPaymentRequest,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY"))
):
    return await partial_payment(
        data.order_id,
        data.customer_id,
        data.amount
    )

@router.get("/")
async def list_payments_by_customer(
    customer_id: str = Query(...),
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY"))
):
    return await get_payments_by_customer(customer_id)