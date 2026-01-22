from fastapi import APIRouter
from app.schemas.inventory_itemdetails import InventoryItemDetailCreate, InventoryItemDetailResponse
from app.services.inventory_itemdetails_service import add_inventory_movement

router = APIRouter(prefix="/inventory-movement", tags=["Inventory Movement"])


@router.post("/", response_model=InventoryItemDetailResponse)
async def add_movement(data: InventoryItemDetailCreate):
    return await add_inventory_movement(data.dict())
