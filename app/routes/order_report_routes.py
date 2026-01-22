from fastapi import APIRouter, Depends
from app.services.order_report_service import get_today_orders_for_customer
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/order-reports", tags=["Order Reports"])


@router.get("/today/{customer_id}")
async def today_orders(
    customer_id: str,
    current_user=Depends(require_roles("SUPERADMIN"))
):
    return await get_today_orders_for_customer(customer_id)
