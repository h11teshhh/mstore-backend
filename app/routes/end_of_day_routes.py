from fastapi import APIRouter
from app.services.end_of_day_service import end_of_day_summary

router = APIRouter(prefix="/reports/end-of-day", tags=["End Of Day"])


@router.get("/summary")
async def end_day_summary():
    return await end_of_day_summary()
