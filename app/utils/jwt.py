from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from jose import JWTError, jwt
from app.config import SECRET_KEY, ALGORITHM  # assuming these exist

def get_token_expiry():
    """Midnight IST for daily logout"""
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return midnight

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = get_token_expiry()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
