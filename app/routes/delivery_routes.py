from fastapi import APIRouter
from app.services.delivery_service import get_today_delivery_list

router = APIRouter(prefix="/delivery", tags=["Delivery"])


@router.get("/today")
async def today_delivery():
    return await get_today_delivery_list()
