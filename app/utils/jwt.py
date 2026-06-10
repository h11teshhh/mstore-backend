from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.config import SECRET_KEY, ALGORITHM


def get_token_expiry():
    """Returns next 12:00 AM IST as the token expiry."""
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return midnight


def create_daily_token(data: dict) -> str:
    """Creates a JWT that expires at midnight IST."""
    to_encode = data.copy()
    to_encode.update({"exp": get_token_expiry()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict) -> str:
    """Alias for create_daily_token — backward compatibility."""
    return create_daily_token(data)


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT.
    Raises HTTP 401 on invalid/expired token instead of returning None,
    so callers never receive a None payload.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please login again."
        )
