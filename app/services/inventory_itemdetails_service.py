from bson import ObjectId
from fastapi import HTTPException

from app.database import inventory_itemdetails_collection
from app.services.inventory_stock_service import get_current_stock
from app.utils.time_utils import get_ist_now  # ✅ IST time utility


async def add_inventory_movement(data: dict, current_user_id: str):
    item_id = data["item_id"]
    quantity = data["quantity"]
    movement_type = data["movement_type"]

    try:
        user_obj_id = ObjectId(current_user_id)
        item_obj_id = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # 🔒 BLOCK OUT if insufficient stock
    if movement_type == "OUT":
        current_stock = await get_current_stock(item_id)
        if quantity > current_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Available: {current_stock}"
            )

    now = get_ist_now()  # ✅ IST time

    entry = {
        "item_id": item_obj_id,
        "quantity": quantity,
        "movement_type": movement_type,
        "created_by": user_obj_id,   # ✅ actual logged-in user
        "created_at": now,
        "updated_at": now
    }

    result = await inventory_itemdetails_collection.insert_one(entry)

    return {
        "id": str(result.inserted_id),
        "item_id": item_id,
        "quantity": quantity,
        "movement_type": movement_type,
        "created_by": str(user_obj_id),
        "created_at": entry["created_at"],
        "updated_at": entry["updated_at"]
    }
