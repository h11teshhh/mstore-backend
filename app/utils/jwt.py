from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status
from zoneinfo import ZoneInfo

from app.config import SECRET_KEY, ALGORITHM


def create_daily_token(data: dict) -> str:
    """
    Creates a token that expires at 12:00 AM (midnight IST)
    """

    # 1️⃣ Get current UTC time
    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))

    # 2️⃣ Convert to IST
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    # 3️⃣ Calculate next IST midnight
    next_midnight_ist = (now_ist + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # 4️⃣ Convert IST midnight back to UTC for JWT exp
    next_midnight_utc = next_midnight_ist.astimezone(ZoneInfo("UTC"))

    payload = data.copy()
    payload["exp"] = next_midnight_utc

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
