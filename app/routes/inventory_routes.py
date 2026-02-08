from fastapi import APIRouter, Depends
from app.schemas.inventory import InventoryCreate, InventoryResponse
from app.services.inventory_service import create_inventory_item
from app.services.inventory_stock_service import get_inventory_with_stock
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/", response_model=InventoryResponse)
async def add_inventory(
    item: InventoryCreate,
    current_user=Depends(require_roles("SUPERADMIN"))
):
    return await create_inventory_item(item.dict(), current_user)


@router.get("/stock")
async def list_inventory_with_stock():
    """
    Used by UI to show available items while creating orders.
    """
    return await get_inventory_with_stock()
