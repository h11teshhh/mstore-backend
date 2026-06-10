# Updated with IST timezone for daily logout

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def get_token_expiry():
    # Midnight IST
    now = datetime.now(ZoneInfo('Asia/Kolkata'))
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return midnight