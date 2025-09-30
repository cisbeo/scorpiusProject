"""Mistral AI service wrapper for LLM and embedding operations."""

import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import asyncio
from datetime import datetime
import hashlib
import json

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import time
import redis.asyncio as redis

from src.core.ai_config import ai_config
from src.services.ai.embedding_cache import EmbeddingCacheService, get_embedding_cache

logger = logging.getLogger(__name__)


class MistralAIService:
    """Service wrapper for Mistral AI operations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Mistral AI service.

        Args:
            config: Optional configuration override
        """
        self.config = config or ai_config.get_llm_config()
        self.embedding_config = ai_config.get_embedding_config()

        self._llm = None
        self._embed_model = None
        self._settings = None
        self._embedding_cache = None

        # Token usage tracking
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.request_count = 0
        self.cache_saves = 0  # Track API calls saved by cache

        # Cost per 1M tokens (approximate)
        self.cost_per_million_tokens = {
            "mistral-large-latest": 8.0,  # $8 per 1M tokens
            "mistral-medium-latest": 2.7,  # $2.7 per 1M tokens
            "mistral-small-latest": 1.0,  # $1 per 1M tokens
            "mistral-embed": 0.1,  # $0.1 per 1M tokens
        }

        # Initialize models
        self._initialize_models()

        # Initialize cache asynchronously (will be done on first use)
        asyncio.create_task(self._initialize_cache())

    def _initialize_models(self):
        """Initialize native Mistral AI client."""
        try:
            from mistralai import Mistral

            # Initialize Mistral client
            self._client = Mistral(
                api_key=self.config["api_key"]
            )

            # Store model names
            self._llm_model = self.config["model"]
            self._embed_model_name = self.embedding_config["model"]

            logger.info(f"Mistral AI service initialized with model: {self.config['model']}")

        except ImportError as e:
            logger.error(f"Failed to import Mistral AI libraries: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Mistral AI service: {e}")
            raise

    async def _initialize_cache(self):
        """Initialize embedding cache service."""
        try:
            # Try to connect to Redis
            redis_client = None
            if ai_config.enable_query_cache:
                try:
                    redis_client = redis.from_url(
                        "redis://redis:6379",
                        encoding="utf-8",
                        decode_responses=False  # Need binary for pickle
                    )
                    await redis_client.ping()
                    logger.info("Connected to Redis for embedding cache")
                except Exception as e:
                    logger.warning(f"Could not connect to Redis: {e}")

            # Create cache service
            self._embedding_cache = await get_embedding_cache(redis_client)

        except Exception as e:
            logger.warning(f"Failed to initialize embedding cache: {e}")
            # Continue without cache
            self._embedding_cache = None

    async def _ensure_cache(self):
        """Ensure cache is initialized before use."""
        if self._embedding_cache is None and ai_config.enable_query_cache:
            await self._initialize_cache()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def generate_embedding(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single text with caching.

        Args:
            text: Text to embed
            metadata: Optional metadata for tracking
            use_cache: Whether to use cache

        Returns:
            Embedding vector
        """
        # Ensure cache is initialized
        await self._ensure_cache()

        # Try to get from cache first
        if use_cache and self._embedding_cache:
            cached_embedding = await self._embedding_cache.get_embedding(
                text, self._embed_model_name
            )
            if cached_embedding:
                self.cache_saves += 1
                logger.debug(f"Using cached embedding (saved {self.cache_saves} API calls)")
                return cached_embedding

        try:
            # Use native Mistral client for embeddings
            response = await asyncio.to_thread(
                self._client.embeddings.create,
                model=self._embed_model_name,
                inputs=[text]
            )

            # Extract embedding from response
            embedding = response.data[0].embedding

            # Cache the embedding for future use
            if use_cache and self._embedding_cache:
                await self._embedding_cache.set_embedding(
                    text, embedding, self._embed_model_name
                )

            # Track usage
            self._track_embedding_usage(text)

            return embedding

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"Rate limit hit, will retry with backoff: {e}")
                # Add extra delay for rate limits
                await asyncio.sleep(2)
            else:
                logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = True,
        delay_between_batches: float = 2.0,
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches with caching and rate limit handling.

        Args:
            texts: List of texts to embed
            batch_size: Batch size (default from config, max 5 for rate limits)
            show_progress: Show progress bar
            delay_between_batches: Delay in seconds between batches
            use_cache: Whether to use cache

        Returns:
            List of embedding vectors
        """
        # Ensure cache is initialized
        await self._ensure_cache()

        # First, try to get cached embeddings
        embeddings_dict = {}
        uncached_texts = texts

        if use_cache and self._embedding_cache:
            cached_embeddings, uncached_texts = await self._embedding_cache.get_batch_embeddings(
                texts, self._embed_model_name
            )
            embeddings_dict = cached_embeddings

            if cached_embeddings:
                self.cache_saves += len(cached_embeddings)
                logger.info(
                    f"Retrieved {len(cached_embeddings)} embeddings from cache, "
                    f"{len(uncached_texts)} need to be generated"
                )

        # Generate embeddings for uncached texts
        if uncached_texts:
            # Reduce batch size to avoid rate limits (max 5)
            default_batch_size = self.embedding_config.get("batch_size", 10)
            batch_size = min(batch_size or default_batch_size, 5)
            new_embeddings = []
            total_batches = (len(uncached_texts) + batch_size - 1) // batch_size

            logger.info(f"Processing {len(uncached_texts)} uncached texts in {total_batches} batches of {batch_size}")

            for i in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[i:i + batch_size]
                batch_num = i // batch_size + 1

                if show_progress:
                    logger.info(f"Processing batch {batch_num}/{total_batches}")

                try:
                    # Process batch sequentially to reduce concurrent API calls
                    batch_embeddings = []
                    for text in batch:
                        # Generate without cache lookup (already checked)
                        embedding = await self.generate_embedding(text, use_cache=False)
                        batch_embeddings.append(embedding)
                        embeddings_dict[text] = embedding
                        new_embeddings.append((text, embedding))
                        # Small delay between individual calls
                        await asyncio.sleep(0.2)

                    # Delay between batches to respect rate limits
                    if i + batch_size < len(uncached_texts):  # Not the last batch
                        logger.debug(f"Waiting {delay_between_batches}s before next batch...")
                        await asyncio.sleep(delay_between_batches)

                except Exception as e:
                    logger.error(f"Failed to process batch {batch_num}: {e}")
                    # On error, increase delay before retry
                    await asyncio.sleep(delay_between_batches * 2)
                    raise

            # Cache the newly generated embeddings
            if use_cache and self._embedding_cache and new_embeddings:
                cached_count = await self._embedding_cache.set_batch_embeddings(
                    new_embeddings, self._embed_model_name
                )
                logger.info(f"Cached {cached_count} new embeddings")

        # Return embeddings in the original order
        result = []
        for text in texts:
            if text in embeddings_dict:
                result.append(embeddings_dict[text])
            else:
                logger.error(f"Missing embedding for text: {text[:50]}...")
                # This shouldn't happen, but handle it gracefully
                result.append([0.0] * self.embedding_config["dimension"])

        logger.info(
            f"Successfully returned {len(result)} embeddings "
            f"(saved {self.cache_saves} API calls total)"
        )
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False
    ) -> Union[str, asyncio.StreamReader]:
        """
        Generate completion using Mistral LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            max_tokens: Maximum tokens to generate
            temperature: Temperature for sampling
            stream: Stream the response

        Returns:
            Generated text or stream
        """
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Use native Mistral client
            if stream:
                # Stream not implemented for now
                raise NotImplementedError("Streaming is not implemented yet")
            else:
                response = await asyncio.to_thread(
                    self._client.chat.complete,
                    model=self._llm_model,
                    messages=messages,
                    max_tokens=max_tokens or self.config.get("max_tokens", 2000),
                    temperature=temperature or self.config.get("temperature", 0.1)
                )

                # Extract content from response
                content = response.choices[0].message.content

                # Track usage
                self._track_completion_usage(prompt, content)

                return content

        except Exception as e:
            logger.error(f"Failed to generate completion: {e}")
            raise

    async def analyze_procurement_document(
        self,
        text: str,
        document_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Analyze a procurement document with specialized prompts.

        Args:
            text: Document text
            document_type: Type of document (CCTP, CCAP, etc.)

        Returns:
            Analysis results
        """
        system_prompt = """Tu es un expert en marchés publics français.
        Analyse le document fourni et extrais les informations clés suivantes:
        1. Type de marché et objet
        2. Exigences techniques principales
        3. Critères de sélection
        4. Budget et délais
        5. Points d'attention particuliers

        Réponds en JSON structuré."""

        prompt = f"""Analyse ce document de type {document_type}:

        {text[:3000]}  # Limit to avoid token limits

        Extrais les informations clés en format JSON."""

        try:
            response = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1  # Low temperature for factual extraction
            )

            # Parse JSON response
            try:
                analysis = json.loads(response)
            except json.JSONDecodeError:
                # Fallback to text response
                analysis = {"raw_analysis": response}

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze procurement document: {e}")
            return {"error": str(e)}

    def _track_embedding_usage(self, text: str):
        """Track token usage for embeddings."""
        # Approximate token count (1 token ≈ 4 characters)
        token_count = len(text) // 4
        self.total_tokens_used += token_count

        # Calculate cost
        model = self.embedding_config["model"]
        cost_per_token = self.cost_per_million_tokens.get(model, 0.1) / 1_000_000
        cost = token_count * cost_per_token
        self.total_cost_usd += cost

        self.request_count += 1

        # Log if approaching limits
        if self.total_cost_usd > ai_config.max_monthly_cost_usd * 0.8:
            logger.warning(f"Approaching monthly cost limit: ${self.total_cost_usd:.2f}")

    def _track_completion_usage(self, prompt: str, response: str):
        """Track token usage for completions."""
        # Approximate token count
        prompt_tokens = len(prompt) // 4
        response_tokens = len(response) // 4
        total_tokens = prompt_tokens + response_tokens

        self.total_tokens_used += total_tokens

        # Calculate cost
        model = self.config["model"]
        cost_per_token = self.cost_per_million_tokens.get(model, 8.0) / 1_000_000
        cost = total_tokens * cost_per_token
        self.total_cost_usd += cost

        self.request_count += 1

        # Log usage
        logger.debug(f"Completion used {total_tokens} tokens, cost: ${cost:.4f}")

    async def create_query_hash(self, query: str) -> str:
        """
        Create a hash for query caching.

        Args:
            query: Query text

        Returns:
            SHA-256 hash
        """
        # Include model in hash for cache invalidation on model change
        cache_key = f"{self.config['model']}:{query}"
        return hashlib.sha256(cache_key.encode()).hexdigest()

    async def check_health(self) -> Dict[str, Any]:
        """
        Check service health and status.

        Returns:
            Health status dictionary
        """
        try:
            # Try a simple embedding
            test_embedding = await self.generate_embedding("test")

            return {
                "status": "healthy",
                "model": self.config["model"],
                "embedding_model": self.embedding_config["model"],
                "total_requests": self.request_count,
                "total_tokens": self.total_tokens_used,
                "total_cost_usd": round(self.total_cost_usd, 2),
                "cost_percentage": round(
                    (self.total_cost_usd / ai_config.max_monthly_cost_usd) * 100, 2
                )
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics including cache performance.

        Returns:
            Usage statistics
        """
        stats = {
            "total_requests": self.request_count,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": round(self.total_cost_usd, 2),
            "average_tokens_per_request": (
                self.total_tokens_used // self.request_count
                if self.request_count > 0 else 0
            ),
            "cost_per_request": (
                self.total_cost_usd / self.request_count
                if self.request_count > 0 else 0
            ),
            "remaining_budget": round(
                ai_config.max_monthly_cost_usd - self.total_cost_usd, 2
            ),
            "cache_saves": self.cache_saves,
            "estimated_savings_usd": round(
                self.cache_saves * 0.0001, 2  # Approximate cost per embedding
            )
        }

        # Add cache stats if available
        if self._embedding_cache:
            stats["cache_stats"] = self._embedding_cache.get_stats()

        return stats

    def reset_usage_stats(self):
        """Reset usage statistics (e.g., monthly reset)."""
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self.request_count = 0
        logger.info("Usage statistics reset")


# Singleton instance
_mistral_service_instance = None


def get_mistral_service() -> MistralAIService:
    """Get or create MistralAI service singleton."""
    global _mistral_service_instance
    if _mistral_service_instance is None:
        _mistral_service_instance = MistralAIService()
    return _mistral_service_instance