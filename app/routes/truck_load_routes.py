from fastapi import APIRouter
from app.services.truck_load_service import get_today_truck_load

router = APIRouter(prefix="/reports/truck-load", tags=["Truck Load"])


@router.get("/today")
async def today_truck_load():
    return await get_today_truck_load()
