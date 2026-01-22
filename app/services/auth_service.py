from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.database import users_collection
from app.utils.auth import hash_password, verify_password
from app.utils.jwt import create_daily_token



async def create_superadmin():
    existing = await users_collection.find_one({"role": "SUPERADMIN"})
    if existing:
        return

    await users_collection.insert_one({
        "name": "Super Admin",
        "mobile": "9978310997",
        "address": "SuperShop",
        "role": "SUPERADMIN",
        "password_hash": hash_password("superadmin@123"),
        "is_active": True,
        "created_by": "system",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })


async def login_user(mobile: str, password: str):
    user = await users_collection.find_one({"mobile": mobile, "is_active": True})
    if not user:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = create_daily_token({
        "user_id": str(user["_id"]),
        "role": user["role"],
        "name": user["name"]
    })

    return {
        "name": user["name"],
        "role": user["role"],
        "expires_at": "12:00 AM",
        "token_type": "bearer",
        "access_token": token, 
        
    }
