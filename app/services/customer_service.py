from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError
from app.database import customers_collection




async def create_customer(data: dict, current_user_id: str):
    customer = {
        "role": "customer",
        "name": data["name"],
        "mobile": data["mobile"],
        "area": data["area"],
        "current_due": 0,
        "is_active": True,
        "created_by": ObjectId(current_user_id),
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
    "current_due": customer["current_due"],
    "is_active": customer["is_active"],
    "created_at": customer["created_at"],
    "updated_at": customer["updated_at"],
}


async def get_all_customers():
    customers = []
    async for c in customers_collection.find({"is_active": True}):
        updated_at = c.get("updated_at") or c.get("created_at") or datetime.utcnow()

        customers.append({
            "id": str(c["_id"]),
            "role": c.get("role", "customer"),
            "name": c.get("name"),
            "mobile": c.get("mobile"),
            "area": c.get("area"),
            "current_due": c.get("current_due", 0),
            "is_active": c.get("is_active", True),
            "created_at": c.get("created_at"),
            "updated_at": updated_at
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

async def get_customer_by_id(customer_id: str):
    try:
        obj_id = ObjectId(customer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid customer_id")

    customer = await customers_collection.find_one({"_id": obj_id})

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer["id"] = str(customer["_id"])
    del customer["_id"]

    if "updated_at" not in customer or customer["updated_at"] is None:
        customer["updated_at"] = customer.get("created_at", datetime.utcnow())

    return customer