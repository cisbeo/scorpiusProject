"""AI and RAG configuration management."""

import os
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class EmbeddingModel(str, Enum):
    """Available embedding models."""
    MISTRAL_EMBED = "mistral-embed"
    OPENAI_ADA = "text-embedding-ada-002"
    LOCAL_SENTENCE_TRANSFORMER = "all-MiniLM-L6-v2"


class LLMModel(str, Enum):
    """Available LLM models."""
    MISTRAL_LARGE = "mistral-large-latest"
    MISTRAL_MEDIUM = "mistral-medium-latest"
    MISTRAL_SMALL = "mistral-small-latest"
    MISTRAL_7B = "open-mistral-7b"
    GPT4 = "gpt-4"
    GPT35_TURBO = "gpt-3.5-turbo"


class ChunkingStrategy(str, Enum):
    """Document chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    HYBRID = "hybrid"


class QueryStrategy(str, Enum):
    """Query processing strategies."""
    SIMPLE = "simple"
    SUBQUESTION = "subquestion"
    ROUTER = "router"
    AGENT = "agent"


class AIConfig(BaseSettings):
    """AI and RAG configuration settings."""

    # API Keys
    mistral_api_key: str = Field(
        default="",
        description="Mistral AI API key",
        alias="MISTRAL_API_KEY"
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (optional)",
        alias="OPENAI_API_KEY"
    )

    # Model Selection
    embedding_model: EmbeddingModel = Field(
        default=EmbeddingModel.MISTRAL_EMBED,
        description="Embedding model to use",
        alias="EMBEDDING_MODEL"
    )

    llm_model: LLMModel = Field(
        default=LLMModel.MISTRAL_LARGE,
        description="LLM model to use",
        alias="LLM_MODEL"
    )

    # Vector Database
    vector_dimension: int = Field(
        default=1024,
        description="Dimension of vector embeddings",
        alias="VECTOR_DIMENSION"
    )

    hnsw_m: int = Field(
        default=16,
        alias="HNSW_M",
        description="HNSW index parameter M"
    )

    hnsw_ef_construction: int = Field(
        default=64,
        alias="HNSW_EF_CONSTRUCTION",
        description="HNSW index parameter ef_construction"
    )

    hnsw_ef_search: int = Field(
        default=40,
        alias="HNSW_EF_SEARCH",
        description="HNSW index parameter ef_search"
    )

    # Chunking Configuration
    chunking_strategy: ChunkingStrategy = Field(
        default=ChunkingStrategy.HYBRID,
        alias="CHUNKING_STRATEGY",
        description="Document chunking strategy"
    )

    chunk_size: int = Field(
        default=512,
        alias="CHUNK_SIZE",
        description="Target chunk size in tokens"
    )

    chunk_overlap: int = Field(
        default=50,
        alias="CHUNK_OVERLAP",
        description="Overlap between chunks in tokens"
    )

    max_chunk_size: int = Field(
        default=1024,
        alias="MAX_CHUNK_SIZE",
        description="Maximum chunk size in tokens"
    )

    # Query Configuration
    default_query_strategy: QueryStrategy = Field(
        default=QueryStrategy.ROUTER,
        alias="DEFAULT_QUERY_STRATEGY",
        description="Default query processing strategy"
    )

    similarity_top_k: int = Field(
        default=5,
        alias="SIMILARITY_TOP_K",
        description="Number of similar chunks to retrieve"
    )

    similarity_threshold: float = Field(
        default=0.7,
        alias="SIMILARITY_THRESHOLD",
        description="Minimum similarity score threshold"
    )

    rerank_top_k: int = Field(
        default=3,
        alias="RERANK_TOP_K",
        description="Number of chunks after reranking"
    )

    # Cache Configuration
    enable_query_cache: bool = Field(
        default=True,
        alias="ENABLE_QUERY_CACHE",
        description="Enable query result caching"
    )

    cache_ttl_seconds: int = Field(
        default=3600,
        alias="CACHE_TTL_SECONDS",
        description="Cache time to live in seconds"
    )

    max_cache_size_mb: int = Field(
        default=100,
        alias="MAX_CACHE_SIZE_MB",
        description="Maximum cache size in MB"
    )

    # Performance Settings
    batch_size: int = Field(
        default=10,
        alias="EMBEDDING_BATCH_SIZE",
        description="Batch size for embedding generation"
    )

    max_concurrent_requests: int = Field(
        default=5,
        alias="MAX_CONCURRENT_REQUESTS",
        description="Maximum concurrent API requests"
    )

    request_timeout_seconds: int = Field(
        default=30,
        alias="REQUEST_TIMEOUT_SECONDS",
        description="API request timeout"
    )

    retry_attempts: int = Field(
        default=3,
        alias="RETRY_ATTEMPTS",
        description="Number of retry attempts for failed requests"
    )

    retry_delay_seconds: int = Field(
        default=1,
        alias="RETRY_DELAY_SECONDS",
        description="Delay between retry attempts"
    )

    # Feature Flags
    enable_rag: bool = Field(
        default=True,
        alias="ENABLE_RAG",
        description="Enable RAG features"
    )

    enable_semantic_search: bool = Field(
        default=True,
        alias="ENABLE_SEMANTIC_SEARCH",
        description="Enable semantic search"
    )

    enable_hybrid_search: bool = Field(
        default=True,
        alias="ENABLE_HYBRID_SEARCH",
        description="Enable hybrid (vector + keyword) search"
    )

    enable_agent: bool = Field(
        default=True,
        alias="ENABLE_AGENT",
        description="Enable agent-based reasoning"
    )

    enable_function_calling: bool = Field(
        default=True,
        alias="ENABLE_FUNCTION_CALLING",
        description="Enable function calling features"
    )

    # Monitoring and Logging
    enable_telemetry: bool = Field(
        default=True,
        alias="ENABLE_TELEMETRY",
        description="Enable telemetry and monitoring"
    )

    log_level: str = Field(
        default="INFO",
        alias="AI_LOG_LEVEL",
        description="Logging level for AI components"
    )

    track_token_usage: bool = Field(
        default=True,
        alias="TRACK_TOKEN_USAGE",
        description="Track token usage for cost monitoring"
    )

    # Cost Management
    max_tokens_per_request: int = Field(
        default=2000,
        alias="MAX_TOKENS_PER_REQUEST",
        description="Maximum tokens per LLM request"
    )

    max_monthly_cost_usd: float = Field(
        default=100.0,
        alias="MAX_MONTHLY_COST_USD",
        description="Maximum monthly cost in USD"
    )

    alert_threshold_percentage: float = Field(
        default=80.0,
        alias="ALERT_THRESHOLD_PERCENTAGE",
        description="Cost alert threshold as percentage of max"
    )

    # French Procurement Specific
    procurement_language: str = Field(
        default="fr",
        alias="PROCUREMENT_LANGUAGE",
        description="Primary language for procurement documents"
    )

    extract_tables: bool = Field(
        default=True,
        alias="EXTRACT_TABLES",
        description="Extract tables from documents"
    )

    extract_requirements: bool = Field(
        default=True,
        alias="EXTRACT_REQUIREMENTS",
        description="Extract requirements automatically"
    )

    compliance_check_enabled: bool = Field(
        default=True,
        alias="COMPLIANCE_CHECK_ENABLED",
        description="Enable automatic compliance checking"
    )

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment

    @validator("mistral_api_key")
    def validate_mistral_key(cls, v: str) -> str:
        """Validate Mistral API key format."""
        if v and not v.startswith("sk-"):
            # Note: Mistral keys might have different formats
            pass  # Just log warning in production
        return v

    @validator("similarity_threshold")
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate similarity threshold is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Similarity threshold must be between 0.0 and 1.0")
        return v

    @validator("chunk_overlap")
    def validate_chunk_overlap(cls, v: int, values: Dict[str, Any]) -> int:
        """Validate chunk overlap is less than chunk size."""
        chunk_size = values.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        return v

    def get_embedding_config(self) -> Dict[str, Any]:
        """Get embedding model configuration."""
        config = {
            "model": self.embedding_model.value,
            "dimension": self.vector_dimension,
            "batch_size": self.batch_size,
        }

        if self.embedding_model == EmbeddingModel.MISTRAL_EMBED:
            config["api_key"] = self.mistral_api_key
        elif self.embedding_model == EmbeddingModel.OPENAI_ADA:
            config["api_key"] = self.openai_api_key

        return config

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        config = {
            "model": self.llm_model.value,
            "max_tokens": self.max_tokens_per_request,
            "temperature": 0.1,  # Low temperature for factual responses
            "timeout": self.request_timeout_seconds,
        }

        if self.llm_model.value.startswith("mistral"):
            config["api_key"] = self.mistral_api_key
        elif self.llm_model.value.startswith("gpt"):
            config["api_key"] = self.openai_api_key

        return config

    def get_vector_store_config(self) -> Dict[str, Any]:
        """Get vector store configuration."""
        return {
            "dimension": self.vector_dimension,
            "hnsw_m": self.hnsw_m,
            "hnsw_ef_construction": self.hnsw_ef_construction,
            "hnsw_ef_search": self.hnsw_ef_search,
            "similarity_top_k": self.similarity_top_k,
            "similarity_threshold": self.similarity_threshold,
        }

    def get_chunking_config(self) -> Dict[str, Any]:
        """Get chunking configuration."""
        return {
            "strategy": self.chunking_strategy.value,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "max_chunk_size": self.max_chunk_size,
        }

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        feature_map = {
            "rag": self.enable_rag,
            "semantic_search": self.enable_semantic_search,
            "hybrid_search": self.enable_hybrid_search,
            "agent": self.enable_agent,
            "function_calling": self.enable_function_calling,
        }
        return feature_map.get(feature, False)


# Global configuration instance
ai_config = AIConfig()
