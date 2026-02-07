from bson import ObjectId
from fastapi import HTTPException

from app.database import inventory_collection
from app.utils.time_utils import get_ist_now  # ✅ IST time utility


async def create_inventory_item(data: dict, current_user_id: str):
    try:
        user_obj_id = ObjectId(current_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    now = get_ist_now()  # ✅ IST time

    item = {
        "item_name": data["item_name"],
        "price": data["price"],
        "is_active": True,
        "created_by": user_obj_id,  # ✅ actual logged-in user
        "created_at": now,
        "updated_at": now
    }

    try:
        result = await inventory_collection.insert_one(item)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Item with this name already exists"
        )

    return {
        "id": str(result.inserted_id),
        "item_name": item["item_name"],
        "price": item["price"],
        "current_stock": 0,   # calculated later via ledger
        "is_active": True
    }
