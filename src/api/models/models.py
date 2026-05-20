"""
Pydantic models for API request/response validation.
"""

import re

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Authentication
    api_key: str = Field(default="", alias="API_KEY")
    require_api_key: bool = Field(default=True, alias="REQUIRE_API_KEY")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    # LLM Configuration
    llm_provider: str = Field(default="openrouter", alias="LLM_PROVIDER")

    # Storage Configuration
    # Local/Docker
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="production_rag_v1", alias="QDRANT_COLLECTION")

    # Cloud (Qdrant Cloud)
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # Neon/Postgres
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "populate_by_name": True,
        "extra": "ignore",
    }


class QueryRequest(BaseModel):
    """Request model for query endpoint."""

    query: str = Field(..., min_length=1, max_length=5000, description="User query text")
    stream: bool = Field(default=False, description="Enable streaming response")
    include_sources: bool = Field(default=True, description="Include source documents in response")
    llm_api_key: str | None = Field(
        default=None,
        description="User's own OpenRouter API key (optional). "
        "If not provided, system attempts Ollama. Key is never stored — used only for this request.",
    )

    model_config = {"json_schema_extra": {"example": {"query": "What is the project about?"}}}

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize query to prevent prompt injection attacks."""
        v = v.strip()
        injection_pattern = re.compile(
            r"(?i)(system\s*[:\n]|ignore\s+(previous|all|above)\s+instructions|"
            r"(sudo|admin|root)\s*(command|query|request)|"
            r"you\s+are\s+(now|a)|return\s+the\s+following)",
            re.IGNORECASE,
        )
        if injection_pattern.search(v):
            raise ValueError("Invalid query pattern detected")
        return v

    @field_validator("llm_api_key")
    @classmethod
    def validate_llm_key(cls, v: str | None) -> str | None:
        """Light validation — let OpenRouter reject invalid keys."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) < 10:
            raise ValueError("LLM API key appears too short")
        return v


class QueryResponse(BaseModel):
    """Response model for query endpoint."""

    answer: str = Field(..., description="Generated answer from RAG pipeline")
    sources: list[dict] | None = Field(default=None, description="Source documents used")
    latency_ms: float = Field(..., description="Total processing latency in milliseconds")
    validation_passed: bool = Field(..., description="Whether response passed validation")


class IngestRequest(BaseModel):
    """Request model for document ingestion."""

    text_content: str = Field(..., description="Raw text content to ingest")
    metadata: dict | None = Field(default=None, description="Optional document metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text_content": "Annual report content goes here...",
                "metadata": {"department": "Academic", "year": "2024"},
            }
        }
    }


class IngestResponse(BaseModel):
    """Response model for document ingestion."""

    status: str = Field(..., description="Ingestion status")
    chunks_created: int = Field(..., description="Number of chunks created")
    document_id: str = Field(..., description="Unique document identifier")


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    components: dict = Field(..., description="Component health status")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error message")
    detail: str | None = Field(default=None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")


class MetadataQueryRequest(BaseModel):
    """Request model for metadata queries."""

    department: str | None = Field(
        default=None,
        description="Filter by department (Financial, Academic, Technical, General)",
    )
    year: str | None = Field(default=None, description="Filter by year (e.g., 2024)")
    source_file: str | None = Field(default=None, description="Filter by source file name (partial match)")
    domain_tag: str | None = Field(default=None, description="Filter by domain tag")
    offset: int = Field(default=0, description="Pagination offset")
    limit: int = Field(default=50, description="Pagination limit (max 100)")


class MetadataChunkResponse(BaseModel):
    """Single chunk in metadata response."""

    id: str = Field(..., description="Chunk ID")
    text: str = Field(..., description="Text content (truncated)")
    source_file: str | None = Field(default=None, description="Source file")
    department: str | None = Field(default=None, description="Department")
    year: str | None = Field(default=None, description="Year/date")
    section_heading: str | None = Field(default=None, description="Section heading")
    domain_tag: str | None = Field(default=None, description="Domain tag")


class MetadataQueryResponse(BaseModel):
    """Response model for metadata queries."""

    total: int = Field(..., description="Total matching records")
    offset: int = Field(..., description="Current offset")
    limit: int = Field(..., description="Current limit")
    chunks: list[MetadataChunkResponse] = Field(default_factory=list, description="Matching chunks")
