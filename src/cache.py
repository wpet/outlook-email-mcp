"""
Cache module for storing API responses.
Provides in-memory caching with TTL support.
"""

import time
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# CACHE STORAGE
# =============================================================================

# Cache storage: {key: (value, expiry_timestamp)}
_cache: dict[str, tuple[Any, float]] = {}


# =============================================================================
# CACHE FUNCTIONS
# =============================================================================

def cache_get(key: str) -> Optional[Any]:
    """
    Get value from cache if not expired.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found/expired
    """
    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            logger.debug(f"Cache hit: {key[:50]}")
            return value
        else:
            del _cache[key]
    return None


def cache_set(key: str, value: Any, ttl: int) -> None:
    """
    Store value in cache with TTL.

    Args:
        key: Cache key
        value: Value to cache
        ttl: Time to live in seconds
    """
    _cache[key] = (value, time.time() + ttl)
    logger.debug(f"Cache set: {key[:50]} (TTL: {ttl}s)")


def cache_clear() -> dict:
    """
    Clear all caches and return stats.

    Returns:
        Dict with number of entries cleared
    """
    global _cache
    stats = {
        "entries_cleared": len(_cache),
    }
    _cache = {}
    logger.info(f"Cache cleared: {stats['entries_cleared']} entries")
    return stats


def cache_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Dict with total, valid, and expired entry counts
    """
    now = time.time()
    valid = sum(1 for _, (_, exp) in _cache.items() if exp > now)
    expired = len(_cache) - valid
    return {
        "total_entries": len(_cache),
        "valid_entries": valid,
        "expired_entries": expired,
    }


def cache_delete(key: str) -> bool:
    """
    Delete a specific key from cache.

    Args:
        key: Cache key to delete

    Returns:
        True if key was deleted, False if not found
    """
    if key in _cache:
        del _cache[key]
        return True
    return False
