from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import inventory_collection

SYSTEM_USER_ID = ObjectId("696f3a0797dacdd4c345551b")


async def create_inventory_item(data: dict):
    item = {
        "item_name": data["item_name"],
        "price": data["price"],
        "is_active": True,
        "created_by": SYSTEM_USER_ID,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
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
