from fastapi import APIRouter, Depends
from app.schemas.stock_adjustment import StockAdjustmentCreate
from app.services.stock_adjustment_service import adjust_stock
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/stock-adjustment", tags=["Stock Adjustment"])


@router.post("/")
async def adjust(
    data: StockAdjustmentCreate,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN"))
):
    return await adjust_stock(data.dict(), current_user)
