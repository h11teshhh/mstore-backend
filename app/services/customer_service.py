from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database import customers_collection

SYSTEM_USER_ID = ObjectId("696f3a0797dacdd4c345551b")


async def create_customer(data: dict):
    customer = {
        "role": "customer",
        "name": data["name"],
        "mobile": data["mobile"],
        "area": data["area"],
        "current_due": 0,
        "is_active": True,
        "created_by": SYSTEM_USER_ID,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    try:
        result = await customers_collection.insert_one(customer)

    except DuplicateKeyError as e:
        # This ONLY triggers if unique index on mobile is violated
        print("❌ DuplicateKeyError:", e)
        raise HTTPException(
            status_code=400,
            detail="Customer with this mobile already exists"
        )

    except PyMongoError as e:
        # Any other MongoDB error (WRITE ERROR, SCHEMA ERROR, ETC.)
        print("❌ PyMongoError:", e)
        raise HTTPException(
            status_code=500,
            detail="Database error while creating customer"
        )

    except Exception as e:
        # Absolutely anything else (coding error, type error, etc.)
        print("❌ Unknown Exception:", e)
        raise HTTPException(
            status_code=500,
            detail="Unexpected server error"
        )

    return {
        "id": str(result.inserted_id),
        "role": "customer",
        "name": customer["name"],
        "mobile": customer["mobile"],
        "area": customer["area"],
        "current_due": 0,
        "is_active": True
    }

async def get_all_customers():
    customers = []
    async for c in customers_collection.find({"is_active": True}):
        customers.append({
            "id": str(c["_id"]),
            "role": c["role"],
            "name": c["name"],
            "mobile": c["mobile"],
            "area": c["area"],
            "current_due": c["current_due"],
            "is_active": c["is_active"]
        })
    return customers


async def update_customer(customer_id: str, data: dict):
    update_data = {k: v for k, v in data.items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    result = await customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Customer not found")

    return {"message": "Customer updated successfully"}
