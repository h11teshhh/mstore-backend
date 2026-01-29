from datetime import datetime
from fastapi import HTTPException
from app.database import users_collection
from app.utils.auth import hash_password


async def create_user(data: dict, current_user: dict):
    if current_user["role"] != "SUPERADMIN":
        raise HTTPException(403, "Only SuperAdmin can create users")

    # validate role
    if data["role"] not in ["SUPERADMIN", "ADMIN", "DELIVERY"]:
        raise HTTPException(400, "Invalid role")

    existing = await users_collection.find_one({"mobile": data["mobile"]})
    if existing:
        raise HTTPException(400, "User already exists")

    result = await users_collection.insert_one({
        "name": data["name"],
        "mobile": data["mobile"],
        "address": data["address"],
        "role": data["role"],  # ✅ use requested role
        "password_hash": hash_password(data["password"]),
        "is_active": True,
        "created_by": current_user["id"],  # ✅ correct key
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })

    return {
        "message": "User created successfully",
        "user_id": str(result.inserted_id)
    }