from fastapi import APIRouter, Depends
from app.schemas.inventory_itemdetails import (
    InventoryItemDetailCreate,
    InventoryItemDetailResponse
)
from app.services.inventory_itemdetails_service import add_inventory_movement
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/inventory-movement", tags=["Inventory Movement"])


@router.post("/", response_model=InventoryItemDetailResponse)
async def add_movement(
    data: InventoryItemDetailCreate,
    current_user=Depends(require_roles("SUPERADMIN", "ADMIN"))
):
    return await add_inventory_movement(data.dict(), current_user)
