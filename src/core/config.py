"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application Settings
    app_name: str = Field(default="ScorpiusProject", description="Application name")
    app_env: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # API Configuration
    api_version: str = Field(default="v1", description="API version")
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")

    # Database Configuration
    database_url: PostgresDsn = Field(
        default="postgresql://scorpius:scorpius@localhost:5432/scorpius_mvp",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(
        default=40, description="Maximum overflow connections"
    )
    database_pool_timeout: int = Field(
        default=30, description="Pool connection timeout in seconds"
    )

    # Redis Configuration
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_max_connections: int = Field(default=50, description="Maximum Redis connections")
    redis_decode_responses: bool = Field(
        default=True, description="Decode Redis responses"
    )

    # Security
    secret_key: str = Field(
        default="your-secret-key-here-change-in-production",
        description="Application secret key",
    )
    jwt_secret_key: str = Field(
        default="your-jwt-secret-key-here-change-in-production",
        description="JWT secret key",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token expiration in days"
    )
    bcrypt_rounds: int = Field(default=12, description="Bcrypt hashing rounds")

    # CORS Settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow credentials in CORS"
    )
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed CORS methods",
    )
    cors_allow_headers: List[str] = Field(
        default=["*"], description="Allowed CORS headers"
    )

    # File Upload Settings
    max_upload_size: int = Field(
        default=52428800, description="Maximum upload size in bytes (50MB)"
    )
    upload_path: str = Field(default="/app/uploads", description="Upload directory path")
    allowed_extensions: List[str] = Field(
        default=[".pdf"], description="Allowed file extensions"
    )
    temp_path: str = Field(default="/tmp/scorpius", description="Temporary files path")

    # Document Processing
    processing_timeout: int = Field(
        default=30, description="Document processing timeout in seconds"
    )
    max_concurrent_processing: int = Field(
        default=5, description="Maximum concurrent document processing"
    )
    extraction_confidence_threshold: float = Field(
        default=0.7, description="Minimum confidence threshold for extraction"
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(
        default=100, description="Maximum requests per window"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )

    # External Services (Optional for MVP)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key")
    aws_secret_access_key: Optional[str] = Field(
        default=None, description="AWS secret key"
    )
    aws_region: Optional[str] = Field(default="eu-west-1", description="AWS region")
    s3_bucket_name: Optional[str] = Field(default=None, description="S3 bucket name")

    # Monitoring (Optional for MVP)
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    prometheus_enabled: bool = Field(default=False, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus port")

    # Email (Optional for MVP)
    smtp_host: Optional[str] = Field(default=None, description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP user")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_from: str = Field(
        default="noreply@scorpiusproject.fr", description="Default from email"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of {valid_levels}")
        return v.upper()

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate application environment."""
        valid_envs = ["development", "staging", "production", "testing"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid environment. Must be one of {valid_envs}")
        return v.lower()

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        """Validate CORS origins are valid URLs."""
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid CORS origin: {origin}")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.app_env == "testing"

    def get_database_url(self, async_mode: bool = True) -> str:
        """
        Get database URL for sync or async connections.

        Args:
            async_mode: Whether to return async connection string

        Returns:
            Database connection URL
        """
        url = str(self.database_url)
        if async_mode and url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    def get_redis_url(self) -> str:
        """Get Redis connection URL as string."""
        return str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings instance
    """
    return Settings()