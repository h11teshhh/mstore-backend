"""
auth_service.py

Login performance notes:
  1. users_collection has a 'mobile' index (created in db_indexes.py) so the
     find() call is an indexed point-lookup — fast even on large collections.
  2. pbkdf2_sha256 password verification is intentionally CPU-intensive
     (~200-400ms). We run it in asyncio's thread executor so it does NOT block
     the event loop and FastAPI can serve other requests during verification.
  3. First-request latency on Render free tier is caused by container cold start
     (10-30s). Once warm, login is fast. The loading indicator on the client
     communicates this to the user.
"""
import asyncio
from datetime import datetime
from fastapi import HTTPException
from app.database import users_collection
from app.utils.auth import hash_password, verify_password
from app.utils.jwt import create_daily_token


async def create_superadmin():
    existing = await users_collection.find_one({"role": "SUPERADMIN"})
    if existing:
        return
    await users_collection.insert_one({
        "name":          "Super Admin",
        "mobile":        "9978310997",
        "address":       "SuperShop",
        "role":          "SUPERADMIN",
        "password_hash": hash_password("superadmin@123"),
        "is_active":     True,
        "created_by":    "system",
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
    })


async def login_user(mobile: str, password: str):
    # Indexed find — fast
    user = await users_collection.find_one({"mobile": mobile, "is_active": True})
    if not user:
        raise HTTPException(401, "Invalid mobile number or password")

    # Run CPU-intensive bcrypt/pbkdf2 verify in thread pool
    # so the async event loop is never blocked
    loop = asyncio.get_running_loop()
    try:
        is_valid = await loop.run_in_executor(
            None, verify_password, password, user["password_hash"]
        )
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(401, "Invalid mobile number or password")

    token = create_daily_token({
        "user_id": str(user["_id"]),
        "role":    user["role"],
        "name":    user["name"],
    })

    return {
        "name":         user["name"],
        "role":         user["role"],
        "expires_at":   "12:00 AM IST",
        "token_type":   "bearer",
        "access_token": token,
    }
