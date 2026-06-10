from fastapi import APIRouter, Depends, HTTPException
from app.schemas.inventory import InventoryCreate, InventoryResponse
from app.services.inventory_service import create_inventory_item
from app.services.inventory_stock_service import get_inventory_with_stock
from app.dependencies.roles import require_roles
from app.database import inventory_collection
from datetime import datetime

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


# DELETE for SUPERADMIN - soft delete item to preserve inventory history, stock calculations, reports
@router.delete("/{item_id}", dependencies=[Depends(require_roles("SUPERADMIN"))])
async def delete_inventory_item(item_id: str):
    if inventory_collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    from bson import ObjectId
    try:
        obj_id = ObjectId(item_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid item ID format")
    
    item = await inventory_collection.find_one({"_id": obj_id})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Soft delete
    result = await inventory_collection.update_one(
        {"_id": obj_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Item deleted successfully (deactivated). Stock history and reports preserved.", "item_id": item_id}
