from fastapi import(APIRouter, Depends , Query)
from app.schemas.order import OrderCreate
from app.services.order_service import (create_order,get_orders_by_customer)

from app.dependencies.roles import require_roles

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/")
async def place_order(
    order: OrderCreate,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN"))
):
    return await create_order(order.dict(), current_user)

@router.get("/")
async def list_orders_by_customer(customer_id: str = Query(...)):
    return await get_orders_by_customer(customer_id)