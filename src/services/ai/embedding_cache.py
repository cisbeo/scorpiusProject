"""Redis-based caching service for embeddings to reduce API calls."""

import hashlib
import json
import logging
import pickle
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
from datetime import datetime, timedelta

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class EmbeddingCacheService:
    """Service for caching embeddings in Redis to reduce API calls."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        cache_prefix: str = "embed",
        ttl_hours: int = 24 * 7  # 1 week default
    ):
        """
        Initialize the embedding cache service.

        Args:
            redis_client: Redis client instance
            cache_prefix: Prefix for cache keys
            ttl_hours: Time to live in hours for cached embeddings
        """
        self.redis_client = redis_client
        self.cache_prefix = cache_prefix
        self.ttl_seconds = ttl_hours * 3600
        self.enabled = ai_config.enable_query_cache and redis_client is not None

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0

        if self.enabled:
            logger.info(f"Embedding cache initialized with {ttl_hours}h TTL")
        else:
            logger.warning("Embedding cache disabled or Redis not available")

    def _generate_cache_key(self, text: str, model: str = "mistral-embed") -> str:
        """
        Generate a cache key for the embedding.

        Args:
            text: Text to embed
            model: Model name for cache invalidation

        Returns:
            Cache key
        """
        # Create hash of text and model
        content = f"{model}:{text}"
        text_hash = hashlib.sha256(content.encode()).hexdigest()
        return f"{self.cache_prefix}:{model}:{text_hash}"

    async def get_embedding(
        self,
        text: str,
        model: str = "mistral-embed"
    ) -> Optional[List[float]]:
        """
        Get cached embedding if available.

        Args:
            text: Text to get embedding for
            model: Model name

        Returns:
            Embedding vector if cached, None otherwise
        """
        if not self.enabled:
            return None

        self.total_requests += 1
        cache_key = self._generate_cache_key(text, model)

        try:
            # Try to get from cache
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                # Deserialize the embedding
                embedding = pickle.loads(cached_data)
                self.cache_hits += 1
                logger.debug(f"Cache hit for embedding (hit rate: {self.get_hit_rate():.1%})")
                return embedding
            else:
                self.cache_misses += 1
                logger.debug(f"Cache miss for embedding")
                return None

        except RedisError as e:
            logger.error(f"Redis error retrieving embedding: {e}")
            return None
        except Exception as e:
            logger.error(f"Error deserializing cached embedding: {e}")
            return None

    async def set_embedding(
        self,
        text: str,
        embedding: List[float],
        model: str = "mistral-embed"
    ) -> bool:
        """
        Cache an embedding.

        Args:
            text: Original text
            embedding: Embedding vector
            model: Model name

        Returns:
            True if cached successfully
        """
        if not self.enabled:
            return False

        cache_key = self._generate_cache_key(text, model)

        try:
            # Serialize and store the embedding
            serialized = pickle.dumps(embedding)
            await self.redis_client.setex(
                cache_key,
                self.ttl_seconds,
                serialized
            )
            logger.debug(f"Cached embedding (size: {len(embedding)})")
            return True

        except RedisError as e:
            logger.error(f"Redis error caching embedding: {e}")
            return False
        except Exception as e:
            logger.error(f"Error serializing embedding: {e}")
            return False

    async def get_batch_embeddings(
        self,
        texts: List[str],
        model: str = "mistral-embed"
    ) -> Tuple[Dict[str, List[float]], List[str]]:
        """
        Get cached embeddings for multiple texts.

        Args:
            texts: List of texts
            model: Model name

        Returns:
            Tuple of (cached_embeddings dict, uncached_texts list)
        """
        if not self.enabled:
            return {}, texts

        cached_embeddings = {}
        uncached_texts = []

        try:
            # Create pipeline for batch get
            pipe = self.redis_client.pipeline()
            cache_keys = []

            for text in texts:
                cache_key = self._generate_cache_key(text, model)
                cache_keys.append(cache_key)
                pipe.get(cache_key)

            # Execute pipeline
            results = await pipe.execute()

            # Process results
            for text, cache_key, result in zip(texts, cache_keys, results):
                self.total_requests += 1
                if result:
                    try:
                        embedding = pickle.loads(result)
                        cached_embeddings[text] = embedding
                        self.cache_hits += 1
                    except Exception as e:
                        logger.error(f"Error deserializing batch embedding: {e}")
                        uncached_texts.append(text)
                        self.cache_misses += 1
                else:
                    uncached_texts.append(text)
                    self.cache_misses += 1

            if cached_embeddings:
                logger.info(
                    f"Batch cache: {len(cached_embeddings)} hits, "
                    f"{len(uncached_texts)} misses "
                    f"(hit rate: {self.get_hit_rate():.1%})"
                )

            return cached_embeddings, uncached_texts

        except RedisError as e:
            logger.error(f"Redis error in batch get: {e}")
            return {}, texts

    async def set_batch_embeddings(
        self,
        text_embedding_pairs: List[Tuple[str, List[float]]],
        model: str = "mistral-embed"
    ) -> int:
        """
        Cache multiple embeddings at once.

        Args:
            text_embedding_pairs: List of (text, embedding) tuples
            model: Model name

        Returns:
            Number of successfully cached embeddings
        """
        if not self.enabled or not text_embedding_pairs:
            return 0

        try:
            # Use pipeline for batch set
            pipe = self.redis_client.pipeline()

            for text, embedding in text_embedding_pairs:
                cache_key = self._generate_cache_key(text, model)
                serialized = pickle.dumps(embedding)
                pipe.setex(cache_key, self.ttl_seconds, serialized)

            # Execute pipeline
            results = await pipe.execute()

            # Count successes
            success_count = sum(1 for r in results if r)

            if success_count > 0:
                logger.info(f"Cached {success_count} embeddings in batch")

            return success_count

        except RedisError as e:
            logger.error(f"Redis error in batch set: {e}")
            return 0

    async def invalidate_cache(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cached embeddings.

        Args:
            pattern: Optional pattern to match keys (e.g., "embed:mistral-embed:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            if pattern:
                search_pattern = pattern
            else:
                search_pattern = f"{self.cache_prefix}:*"

            # Find all matching keys
            keys = []
            async for key in self.redis_client.scan_iter(match=search_pattern):
                keys.append(key)

            # Delete in batches
            deleted = 0
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cached embeddings")

            return deleted

        except RedisError as e:
            logger.error(f"Redis error invalidating cache: {e}")
            return 0

    def get_hit_rate(self) -> float:
        """Get cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "enabled": self.enabled,
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.get_hit_rate():.1%}",
            "ttl_hours": self.ttl_seconds // 3600
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0
        logger.info("Cache statistics reset")

    async def warm_cache(
        self,
        common_texts: List[str],
        embeddings: List[List[float]],
        model: str = "mistral-embed"
    ) -> int:
        """
        Pre-populate cache with common queries.

        Args:
            common_texts: List of common texts
            embeddings: Pre-computed embeddings
            model: Model name

        Returns:
            Number of cached entries
        """
        if not self.enabled:
            return 0

        if len(common_texts) != len(embeddings):
            logger.error("Texts and embeddings count mismatch")
            return 0

        pairs = list(zip(common_texts, embeddings))
        count = await self.set_batch_embeddings(pairs, model)

        logger.info(f"Warmed cache with {count} common embeddings")
        return count

    async def get_cache_size(self) -> Dict[str, Any]:
        """
        Get approximate cache size and memory usage.

        Returns:
            Cache size information
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            # Count keys
            pattern = f"{self.cache_prefix}:*"
            key_count = 0
            total_size = 0

            async for key in self.redis_client.scan_iter(match=pattern):
                key_count += 1
                # Get approximate size
                memory_usage = await self.redis_client.memory_usage(key)
                if memory_usage:
                    total_size += memory_usage

            return {
                "enabled": True,
                "key_count": key_count,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "avg_size_kb": round(total_size / key_count / 1024, 2) if key_count > 0 else 0
            }

        except RedisError as e:
            logger.error(f"Redis error getting cache size: {e}")
            return {"enabled": True, "error": str(e)}


# Singleton instance
_embedding_cache_instance: Optional[EmbeddingCacheService] = None


async def get_embedding_cache(
    redis_client: Optional[redis.Redis] = None
) -> EmbeddingCacheService:
    """Get or create embedding cache singleton."""
    global _embedding_cache_instance

    if _embedding_cache_instance is None:
        # If no Redis client provided, try to create one
        if redis_client is None and ai_config.enable_query_cache:
            try:
                redis_client = redis.from_url(
                    "redis://localhost:6379",
                    encoding="utf-8",
                    decode_responses=False  # Need binary for pickle
                )
                await redis_client.ping()
                logger.info("Connected to Redis for embedding cache")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
                redis_client = None

        _embedding_cache_instance = EmbeddingCacheService(redis_client)

    return _embedding_cache_instance