from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from jose import JWTError, jwt
from app.config import SECRET_KEY, ALGORITHM  # assuming these exist


def get_token_expiry():
    """Midnight IST for daily logout"""
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return midnight


def create_daily_token(data: dict):
    """Main token creation function (aliased for auth_service.py compatibility)"""
    to_encode = data.copy()
    expire = get_token_expiry()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Keep create_access_token for backward compatibility / other potential calls
def create_access_token(data: dict):
    """Alias for create_daily_token to maintain full compatibility"""
    return create_daily_token(data)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None