import time
from functools import wraps
from .config import settings

_store: dict = {}


def ttl_cache(key_prefix: str):
    """Tiny in-process cache. Swap for Redis in production (same interface)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            key = (key_prefix, repr(kw))
            hit = _store.get(key)
            if hit and hit[0] > time.time():
                return hit[1]
            val = fn(*a, **kw)
            _store[key] = (time.time() + settings.CACHE_TTL_SECONDS, val)
            return val
        return wrapper
    return deco


def clear_cache():
    _store.clear()
