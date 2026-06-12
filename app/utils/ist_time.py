"""
IST (Asia/Kolkata = UTC+5:30) date/time helpers.
All "today" queries MUST use IST midnight boundaries so that data
created before midnight IST does not bleed into the next day's view.
"""
from datetime import datetime, timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def now_ist() -> datetime:
    """Current time in IST (naive datetime)."""
    return datetime.utcnow() + IST_OFFSET


def today_ist_utc_range():
    """
    Returns (start_utc, end_utc) corresponding to
    00:00:00 IST → 23:59:59.999 IST of the current IST calendar day,
    expressed as UTC datetimes for MongoDB queries.

    Example (IST = UTC+5:30):
      IST midnight = UTC 18:30 of the previous calendar day
      So if IST date is 2025-06-15:
        start_utc = 2025-06-14 18:30:00 UTC
        end_utc   = 2025-06-15 18:30:00 UTC
    """
    now_i   = now_ist()
    # Start of current IST calendar day (midnight IST in IST terms)
    ist_midnight = now_i.replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert back to UTC
    start_utc = ist_midnight - IST_OFFSET
    end_utc   = start_utc + timedelta(days=1)
    return start_utc, end_utc


def today_ist_date_str() -> str:
    """Returns IST calendar date as 'YYYY-MM-DD' string."""
    return now_ist().strftime("%Y-%m-%d")
