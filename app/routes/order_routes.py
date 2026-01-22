from fastapi import APIRouter, Depends
from app.schemas.order import OrderCreate
from app.services.order_service import create_order
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/")
async def place_order(
    order: OrderCreate,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN"))
):
    return await create_order(order.dict(), current_user)
