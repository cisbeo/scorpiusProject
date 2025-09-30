"""Cache service for requirements extraction results."""

import hashlib
import json
import logging
from typing import Optional, Dict, Any
from uuid import UUID

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RequirementsCache:
    """Redis-based cache for requirements extraction results."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize requirements cache.

        Args:
            redis_client: Optional Redis client instance
        """
        self.redis = redis_client
        self.ttl = 86400 * 7  # 7 days by default
        self.enabled = redis_client is not None

    def _get_cache_key(self, document_id: UUID) -> str:
        """
        Generate cache key for document.

        Args:
            document_id: Document UUID

        Returns:
            Cache key string
        """
        return f"requirements:extraction:{str(document_id)}"

    async def get(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached extraction result.

        Args:
            document_id: Document UUID

        Returns:
            Cached extraction result or None if not found
        """
        if not self.enabled or not self.redis:
            return None

        try:
            key = self._get_cache_key(document_id)
            data = await self.redis.get(key)

            if data:
                logger.debug(f"Cache hit for document {document_id}")
                return json.loads(data)

            logger.debug(f"Cache miss for document {document_id}")
            return None

        except Exception as e:
            logger.error(f"Cache get failed for document {document_id}: {e}")
            return None

    async def set(
        self,
        document_id: UUID,
        extraction: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store extraction result in cache.

        Args:
            document_id: Document UUID
            extraction: Extraction result to cache
            ttl: Optional custom TTL in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled or not self.redis:
            return False

        try:
            key = self._get_cache_key(document_id)
            data = json.dumps(extraction)
            cache_ttl = ttl or self.ttl

            await self.redis.setex(key, cache_ttl, data)
            logger.debug(f"Cached extraction for document {document_id} (TTL: {cache_ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Cache set failed for document {document_id}: {e}")
            return False

    async def invalidate(self, document_id: UUID) -> bool:
        """
        Remove cached extraction for document.

        Args:
            document_id: Document UUID

        Returns:
            True if invalidated successfully
        """
        if not self.enabled or not self.redis:
            return False

        try:
            key = self._get_cache_key(document_id)
            result = await self.redis.delete(key)

            if result:
                logger.debug(f"Invalidated cache for document {document_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Cache invalidation failed for document {document_id}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching pattern.

        Args:
            pattern: Redis pattern (e.g., "requirements:extraction:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0

        try:
            # Find all matching keys
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )

                if keys:
                    deleted_count += await self.redis.delete(*keys)

                if cursor == 0:
                    break

            logger.info(f"Invalidated {deleted_count} cache entries matching '{pattern}'")
            return deleted_count

        except Exception as e:
            logger.error(f"Pattern invalidation failed for '{pattern}': {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self.enabled or not self.redis:
            return {"enabled": False}

        try:
            info = await self.redis.info("stats")
            memory_info = await self.redis.info("memory")

            # Count requirements cache keys
            cursor = 0
            key_count = 0
            pattern = "requirements:extraction:*"

            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                key_count += len(keys)

                if cursor == 0:
                    break

            return {
                "enabled": True,
                "keys_count": key_count,
                "memory_used": memory_info.get("used_memory_human", "N/A"),
                "hit_rate": info.get("keyspace_hit_ratio", 0),
                "total_connections": info.get("total_connections_received", 0),
                "ttl_seconds": self.ttl
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Singleton instance
_cache_instance: Optional[RequirementsCache] = None


async def get_requirements_cache(
    redis_url: Optional[str] = None
) -> RequirementsCache:
    """
    Get or create requirements cache instance.

    Args:
        redis_url: Optional Redis connection URL

    Returns:
        RequirementsCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        redis_client = None

        if redis_url:
            try:
                redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await redis_client.ping()
                logger.info("Connected to Redis for requirements cache")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
                redis_client = None

        _cache_instance = RequirementsCache(redis_client)

    return _cache_instance