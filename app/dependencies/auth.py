from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.utils.jwt import decode_token
from app.database import users_collection

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = decode_token(token)

    # 🔒 REQUIRED KEYS CHECK
    required_keys = {"user_id", "role", "name"}
    if not required_keys.issubset(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user = await users_collection.find_one({
        "_id": ObjectId(payload["user_id"]),
        "is_active": True
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "role": user["role"],
        "mobile": user["mobile"]
    }
