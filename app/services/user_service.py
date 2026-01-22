from datetime import datetime
from fastapi import HTTPException
from app.database import users_collection
from app.utils.auth import hash_password


async def create_user(data: dict, current_user: dict):
    if current_user["role"] != "SUPERADMIN":
        raise HTTPException(403, "Only SuperAdmin can create users")

    existing = await users_collection.find_one({"mobile": data["mobile"]})
    if existing:
        raise HTTPException(400, "User already exists")

    await users_collection.insert_one({
        "name": data["name"],
        "mobile": data["mobile"],
        "address": data["address"],
        "role": "ADMIN",
        "password_hash": hash_password(data["password"]),
        "is_active": True,

        # ✅ FIX HERE
        "created_by": current_user["id"],

        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })

    return {"message": "User created successfully"}
