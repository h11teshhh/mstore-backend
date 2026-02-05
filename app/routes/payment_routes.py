# app/routes/payment_routes.py

from fastapi import APIRouter, Depends
from app.schemas.payment import CustomerPaymentRequest
from app.services.payment_service import customer_payment
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/payments", tags=["Payments"])


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