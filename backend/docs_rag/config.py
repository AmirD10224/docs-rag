"""Strict pydantic-settings configuration loaded once at app startup."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    anthropic_api_key: SecretStr = SecretStr("")
    cohere_api_key: SecretStr = SecretStr("")
    jina_api_key: SecretStr = SecretStr("")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "docs_rag"

    redis_url: str = "redis://localhost:6379/0"

    app_env: Literal["local", "test", "staging", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_origins: str = "http://localhost:3000"

    embedding_model: str = "jina-embeddings-v3"
    embedding_dimensions: int = Field(default=1024, ge=64, le=4096)
    rerank_model: str = "rerank-v3.5"
    synthesis_model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-sonnet-4-6"

    mock_providers: bool = False
    retrieval_top_k_dense: int = Field(default=50, ge=1, le=200)
    retrieval_top_k_bm25: int = Field(default=50, ge=1, le=200)
    rerank_top_k: int = Field(default=8, ge=1, le=50)
    bm25_corpus_max_chunks: int = Field(default=10000, ge=100, le=200000)
    query_cache_ttl_seconds: int = Field(default=3600, ge=0)
    max_pdf_mb: int = Field(default=25, ge=1, le=200)

    price_claude_input_per_mtok: float = 3.0
    price_claude_output_per_mtok: float = 15.0
    price_jina_per_mtok: float = 0.20
    price_cohere_rerank_per_1k: float = 2.0

    # External-call timeouts (seconds). Tight by default, every call has
    # tenacity retries on top, so a single hung upstream cannot wedge the
    # request thread.
    anthropic_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    qdrant_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    redis_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    url_fetch_timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    url_fetch_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)

    # Rate limiting (per IP). Empty string disables the limit (tests).
    rate_limit_query: str = "30/minute"
    rate_limit_ingest: str = "5/minute"
    rate_limit_default: str = "120/minute"
    daily_cost_cap_usd: float = Field(default=50.0, ge=0.0)

    @property
    def auth_bearer_token(self) -> str | None:
        # When set, all mutating endpoints require Authorization: Bearer <token>.
        # Read separately so the value never appears in repr/dict output.
        import os

        token = os.environ.get("AUTH_BEARER_TOKEN", "").strip()
        return token or None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
