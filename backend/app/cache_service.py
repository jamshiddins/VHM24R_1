"""
Caching service for VHM24R.

This service provides a simple interface for storing and retrieving
arbitrary Python objects in Redis. It serializes values to JSON for
storage and deserializes them upon retrieval. This allows caching of
expensive database queries or computation results to improve
performance.
"""

import json
import os
from typing import Any, Optional

import redis


class CacheService:
    """Redis‑based cache service."""

    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is not set")
        self.redis_client = redis.from_url(redis_url)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache by key.

        Args:
            key: The cache key.

        Returns:
            The deserialized value or None if the key does not exist.
        """
        value = self.redis_client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store a value in the cache with an optional TTL.

        Args:
            key: The cache key.
            value: The Python object to cache (will be serialized to JSON).
            ttl: Time to live in seconds. Defaults to 1 hour.
        """
        serialized = json.dumps(value, default=str)
        self.redis_client.setex(key, ttl, serialized)

    def invalidate(self, pattern: str) -> None:
        """Delete all cache entries matching a pattern.

        Args:
            pattern: A Redis pattern (e.g., "orders:*") to match keys.
        """
        for key in self.redis_client.scan_iter(match=pattern):
            self.redis_client.delete(key)
