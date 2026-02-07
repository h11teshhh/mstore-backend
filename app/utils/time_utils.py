from datetime import datetime
import pytz

# Indian Standard Time timezone
IST = pytz.timezone("Asia/Kolkata")


def get_ist_now():
    """
    Returns timezone-aware IST datetime.
    This will be stored directly in MongoDB.
    Example:
        2026-02-08T00:56:00+05:30
    """
    return datetime.now(IST)


def get_ist_today_range():
    """
    Returns start and end datetime of today in IST.
    Use this for filtering today's data.
    """
    now = get_ist_now()

    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end = start.replace(day=start.day + 1)

    return start, end
