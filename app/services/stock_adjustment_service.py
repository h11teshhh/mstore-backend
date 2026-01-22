from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import inventory_itemdetails_collection
from app.services.inventory_stock_service import get_current_stock

SYSTEM_USER_ID = ObjectId("696f3a0797dacdd4c345551b")


async def adjust_stock(data: dict):
    if data["movement_type"] == "OUT":
        stock = await get_current_stock(data["item_id"])
        if data["quantity"] > stock:
            raise HTTPException(
                status_code=400,
                detail="Insufficient stock for adjustment"
            )

    entry = {
        "item_id": ObjectId(data["item_id"]),
        "quantity": data["quantity"],
        "movement_type": data["movement_type"],
        "reason": data["reason"],
        "created_by": SYSTEM_USER_ID,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    await inventory_itemdetails_collection.insert_one(entry)

    return {"status": "STOCK_ADJUSTED"}
