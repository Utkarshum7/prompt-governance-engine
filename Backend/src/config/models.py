"""Pydantic models for configuration validation."""

from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortkeyConfig(BaseSettings):
    """Portkey AI configuration."""

    api_key: str = Field(..., description="Portkey API key")
    base_url: str = Field(default="https://api.portkey.ai", description="Portkey API base URL")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")

    model_config = SettingsConfigDict(env_prefix="PORTKEY_")


class EmbeddingModelConfig(BaseSettings):
    """Embedding model configuration."""

    primary: str = Field(
        default="@openai/text-embedding-3-small",
        description="Primary embedding model",
    )
    fallback: str = Field(
        default="@openai/text-embedding-3-large",
        description="Fallback embedding model for long prompts",
    )
    batch_size: int = Field(default=100, ge=1, le=200, description="Batch size for embeddings")


class CanonicalizationModelConfig(BaseSettings):
    """Canonicalization model configuration."""

    primary: str = Field(
        default="@openai/gpt-4o-2024-08-06",
        description="Primary canonicalization model",
    )
    alternative: str = Field(
        default="@anthropic/claude-3-5-sonnet-latest",
        description="Alternative model for code-heavy prompts",
    )
    max_tokens: int = Field(default=2000, ge=100, le=8000, description="Max tokens for responses")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Temperature for generation")


class ReasoningModelConfig(BaseSettings):
    """Reasoning model configuration."""

    model: str = Field(default="@openai/o1-mini", description="Reasoning model")
    max_tokens: int = Field(default=1000, ge=100, le=4000, description="Max tokens for responses")


class ModerationModelConfig(BaseSettings):
    """Moderation model configuration."""

    model: str = Field(
        default="@openai/text-moderation-latest",
        description="Content moderation model",
    )


class ModelsConfig(BaseSettings):
    """All model configurations."""

    embedding: EmbeddingModelConfig = Field(default_factory=EmbeddingModelConfig)
    canonicalization: CanonicalizationModelConfig = Field(
        default_factory=CanonicalizationModelConfig
    )
    reasoning: ReasoningModelConfig = Field(default_factory=ReasoningModelConfig)
    moderation: ModerationModelConfig = Field(default_factory=ModerationModelConfig)


class ECRConfig(BaseSettings):
    """ECR configuration."""

    repository: str = Field(..., description="ECR repository URL")
    region: str = Field(default="us-east-2", description="ECR region")


class S3Config(BaseSettings):
    """S3 configuration."""

    bucket: str = Field(..., description="S3 bucket name")
    region: str = Field(default="us-east-2", description="S3 region")


class SecretsManagerConfig(BaseSettings):
    """AWS Secrets Manager configuration."""

    enabled: bool = Field(default=True, description="Enable Secrets Manager integration")
    secret_name: str = Field(
        default="portkey-prompt-parser/secrets",
        description="Secret name in AWS Secrets Manager",
    )


class AWSConfig(BaseSettings):
    """AWS configuration."""

    region: str = Field(default="us-east-2", description="Default AWS region")
    ecr: ECRConfig = Field(..., description="ECR configuration")
    s3: S3Config = Field(..., description="S3 configuration")
    secrets_manager: SecretsManagerConfig = Field(
        default_factory=SecretsManagerConfig, description="Secrets Manager configuration"
    )


class PostgreSQLConfig(BaseSettings):
    """PostgreSQL configuration."""

    host: str = Field(..., description="PostgreSQL host")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    ssl_mode: str = Field(default="require", description="SSL mode")
    pool_size: int = Field(default=20, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(default=10, ge=0, le=50, description="Max overflow connections")

    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql+asyncpg://{self.username}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?ssl={self.ssl_mode}"
        )


class RedisConfig(BaseSettings):
    """Redis configuration."""

    host: str = Field(..., description="Redis host")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    decode_responses: bool = Field(default=True, description="Decode responses as strings")


class QdrantConfig(BaseSettings):
    """Qdrant configuration."""

    host: str = Field(..., description="Qdrant host")
    port: int = Field(default=6333, ge=1, le=65535, description="Qdrant port")
    api_key: Optional[str] = Field(default=None, description="Qdrant API key")


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch configuration."""

    host: str = Field(..., description="Elasticsearch host")
    port: int = Field(default=9200, ge=1, le=65535, description="Elasticsearch port")
    username: Optional[str] = Field(default=None, description="Elasticsearch username")
    password: Optional[str] = Field(default=None, description="Elasticsearch password")


class PineconeConfig(BaseSettings):
    """Pinecone configuration."""

    api_key: str = Field(..., description="Pinecone API key")
    environment: str = Field(..., description="Pinecone environment")
    index_name: str = Field(..., description="Pinecone index name")


class VectorDBConfig(BaseSettings):
    """Vector database configuration."""

    type: Literal["qdrant", "elasticsearch", "pinecone"] = Field(
        default="qdrant", description="Vector DB type"
    )
    qdrant: Optional[QdrantConfig] = Field(default=None, description="Qdrant configuration")
    elasticsearch: Optional[ElasticsearchConfig] = Field(
        default=None, description="Elasticsearch configuration"
    )
    pinecone: Optional[PineconeConfig] = Field(default=None, description="Pinecone configuration")

    @model_validator(mode="after")
    def validate_vector_db_config(self):
        """Validate that the selected vector DB type has configuration."""
        if self.type == "qdrant" and not self.qdrant:
            raise ValueError("Qdrant configuration is required when type is 'qdrant'")
        if self.type == "elasticsearch" and not self.elasticsearch:
            raise ValueError(
                "Elasticsearch configuration is required when type is 'elasticsearch'"
            )
        if self.type == "pinecone" and not self.pinecone:
            raise ValueError("Pinecone configuration is required when type is 'pinecone'")
        return self


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    postgresql: PostgreSQLConfig = Field(..., description="PostgreSQL configuration")
    redis: RedisConfig = Field(..., description="Redis configuration")
    vector_db: VectorDBConfig = Field(..., description="Vector database configuration")


class APIConfig(BaseSettings):
    """API server configuration."""

    host: str = Field(default="0.0.0.0", description="API host address")
    port: int = Field(default=8000, ge=1, le=65535, description="API port")
    rate_limit_per_minute: int = Field(
        default=100, ge=1, le=10000, description="Rate limit per minute"
    )
    max_request_size_mb: int = Field(
        default=10, ge=1, le=100, description="Max request size in MB"
    )


class ClusteringConfig(BaseSettings):
    """Clustering configuration."""

    similarity_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Similarity threshold for clustering"
    )
    confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Confidence threshold for merges"
    )
    batch_size: int = Field(default=100, ge=1, le=500, description="Batch size for clustering")
    max_cluster_size: int = Field(
        default=1000, ge=1, le=10000, description="Max prompts per cluster"
    )


class ProcessingConfig(BaseSettings):
    """Processing configuration."""

    worker_concurrency: int = Field(default=4, ge=1, le=32, description="Worker concurrency")
    batch_size: int = Field(default=100, ge=1, le=500, description="Batch size for processing")
    max_retries: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    retry_backoff_seconds: int = Field(
        default=2, ge=1, le=60, description="Retry backoff in seconds"
    )


class AppConfig(BaseSettings):
    """Application configuration."""

    environment: Literal["dev", "staging", "prod"] = Field(
        default="dev", description="Environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Log level"
    )
    api: APIConfig = Field(default_factory=APIConfig, description="API configuration")
    clustering: ClusteringConfig = Field(
        default_factory=ClusteringConfig, description="Clustering configuration"
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig, description="Processing configuration"
    )


class CloudWatchConfig(BaseSettings):
    """CloudWatch configuration."""

    enabled: bool = Field(default=True, description="Enable CloudWatch logging")
    log_group: str = Field(
        default="/aws/ecs/portkey-prompt-parser", description="CloudWatch log group"
    )
    region: str = Field(default="us-east-2", description="CloudWatch region")


class MetricsConfig(BaseSettings):
    """Metrics configuration."""

    enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    endpoint: str = Field(default="/metrics", description="Metrics endpoint path")
    port: int = Field(default=9090, ge=1, le=65535, description="Metrics port")


class ObservabilityConfig(BaseSettings):
    """Observability configuration."""

    cloudwatch: CloudWatchConfig = Field(
        default_factory=CloudWatchConfig, description="CloudWatch configuration"
    )
    metrics: MetricsConfig = Field(default_factory=MetricsConfig, description="Metrics configuration")


class Settings(BaseSettings):
    """Root settings model."""

    portkey: PortkeyConfig = Field(..., description="Portkey AI configuration")
    models: ModelsConfig = Field(default_factory=ModelsConfig, description="Model configurations")
    aws: AWSConfig = Field(..., description="AWS configuration")
    database: DatabaseConfig = Field(..., description="Database configuration")
    app: AppConfig = Field(default_factory=AppConfig, description="Application configuration")
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig, description="Observability configuration"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

