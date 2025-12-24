"""
Tests for the cache module.
"""

import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from src.cache import cache_get, cache_set, cache_clear, cache_stats, cache_delete


class TestCacheBasics:
    """Basic cache operation tests."""

    def test_cache_set_get(self):
        """Test basic set and get operations."""
        cache_set("test_key", "test_value", ttl=60)
        result = cache_get("test_key")
        assert result == "test_value"

    def test_cache_get_nonexistent(self):
        """Test getting a key that doesn't exist."""
        result = cache_get("nonexistent_key")
        assert result is None

    def test_cache_overwrite(self):
        """Test overwriting an existing key."""
        cache_set("overwrite_key", "first_value", ttl=60)
        cache_set("overwrite_key", "second_value", ttl=60)
        result = cache_get("overwrite_key")
        assert result == "second_value"

    def test_cache_different_types(self):
        """Test caching different data types."""
        # String
        cache_set("string_key", "string_value", ttl=60)
        assert cache_get("string_key") == "string_value"

        # Dict
        cache_set("dict_key", {"nested": "value"}, ttl=60)
        assert cache_get("dict_key") == {"nested": "value"}

        # List
        cache_set("list_key", [1, 2, 3], ttl=60)
        assert cache_get("list_key") == [1, 2, 3]

        # None
        cache_set("none_key", None, ttl=60)
        # Note: None is a valid cached value
        assert cache_get("none_key") is None


class TestCacheExpiry:
    """Cache expiry tests."""

    def test_cache_expiry(self):
        """Test that expired entries are not returned."""
        cache_set("expiry_key", "expiring_value", ttl=1)

        # Should be available immediately
        assert cache_get("expiry_key") == "expiring_value"

        # Wait for expiry
        time.sleep(1.1)

        # Should be expired now
        assert cache_get("expiry_key") is None

    def test_cache_long_ttl(self):
        """Test that long TTL values work correctly."""
        cache_set("long_ttl_key", "long_value", ttl=3600)
        assert cache_get("long_ttl_key") == "long_value"

    def test_cache_zero_ttl(self):
        """Test that zero TTL immediately expires."""
        cache_set("zero_ttl_key", "instant_expire", ttl=0)
        # With TTL=0, the entry expires at current time
        time.sleep(0.01)
        assert cache_get("zero_ttl_key") is None


class TestCacheClear:
    """Cache clear operation tests."""

    def test_cache_clear(self):
        """Test clearing all cache entries."""
        # Add multiple entries
        cache_set("key1", "value1", ttl=60)
        cache_set("key2", "value2", ttl=60)
        cache_set("key3", "value3", ttl=60)

        # Clear cache
        stats = cache_clear()

        # Verify stats
        assert stats["entries_cleared"] == 3

        # Verify all entries are gone
        assert cache_get("key1") is None
        assert cache_get("key2") is None
        assert cache_get("key3") is None

    def test_cache_clear_empty(self):
        """Test clearing an empty cache."""
        cache_clear()  # Ensure empty
        stats = cache_clear()
        assert stats["entries_cleared"] == 0


class TestCacheStats:
    """Cache statistics tests."""

    def test_cache_stats(self):
        """Test cache statistics reporting."""
        cache_clear()

        # Add entries
        cache_set("valid1", "value", ttl=60)
        cache_set("valid2", "value", ttl=60)

        stats = cache_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0

    def test_cache_stats_with_expired(self):
        """Test stats with expired entries."""
        cache_clear()

        cache_set("expires_soon", "value", ttl=1)
        cache_set("stays_valid", "value", ttl=60)

        # Wait for one to expire
        time.sleep(1.1)

        stats = cache_stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 1
        assert stats["expired_entries"] == 1


class TestCacheDelete:
    """Cache delete operation tests."""

    def test_cache_delete_existing(self):
        """Test deleting an existing key."""
        cache_set("delete_me", "value", ttl=60)
        assert cache_get("delete_me") == "value"

        result = cache_delete("delete_me")
        assert result is True
        assert cache_get("delete_me") is None

    def test_cache_delete_nonexistent(self):
        """Test deleting a non-existent key."""
        result = cache_delete("nonexistent")
        assert result is False


class TestCacheConcurrency:
    """Cache concurrent access tests."""

    def test_cache_concurrent_access(self):
        """Test concurrent read/write access to cache."""
        cache_clear()

        def write_cache(i):
            cache_set(f"concurrent_key_{i}", f"value_{i}", ttl=60)
            return cache_get(f"concurrent_key_{i}")

        # Run multiple writes concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(write_cache, range(10)))

        # All writes should succeed
        for i, result in enumerate(results):
            assert result == f"value_{i}"

        # Verify all keys exist
        for i in range(10):
            assert cache_get(f"concurrent_key_{i}") == f"value_{i}"

    def test_cache_concurrent_overwrite(self):
        """Test concurrent overwrites of same key."""
        cache_clear()
        key = "shared_key"

        def overwrite_cache(value):
            cache_set(key, value, ttl=60)
            return True

        # Run multiple overwrites concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(overwrite_cache, range(5)))

        # All should succeed
        assert all(results)

        # Final value should be one of the written values
        final_value = cache_get(key)
        assert final_value in list(range(5))
