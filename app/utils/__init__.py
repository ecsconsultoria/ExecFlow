"""app/utils/__init__.py — shared utility helpers."""
import hashlib
import hmac
from datetime import datetime, timezone, timedelta

TZ_BR = timezone(timedelta(hours=-3))


def now_br() -> datetime:
    """Return current datetime in Brasilia time (naive)."""
    return datetime.now(TZ_BR).replace(tzinfo=None)


def utc_to_br(dt):
    if dt is None:
        return None
    utc = dt.replace(tzinfo=timezone.utc)
    return utc.astimezone(TZ_BR).replace(tzinfo=None)


def make_client_token(quote_id: int, secret: str) -> str:
    return hmac.new(secret.encode(), str(quote_id).encode(), hashlib.sha256).hexdigest()[:24]


__all__ = ["now_br", "utc_to_br", "make_client_token"]
