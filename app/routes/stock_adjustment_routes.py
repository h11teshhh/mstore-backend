from fastapi import APIRouter
from app.schemas.stock_adjustment import StockAdjustmentCreate
from app.services.stock_adjustment_service import adjust_stock

router = APIRouter(prefix="/stock-adjustment", tags=["Stock Adjustment"])


@router.post("/")
async def adjust(data: StockAdjustmentCreate):
    return await adjust_stock(data.dict())
