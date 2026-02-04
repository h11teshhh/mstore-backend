# app/routes/report_routes.py

from fastapi import APIRouter, Depends, Query
from app.services.report_service import get_today_bills_by_area
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/bills/today")
async def today_bills_by_area(
    area: str = Query(...),
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN", "DELIVERY"))
):
    return await get_today_bills_by_area(area)
