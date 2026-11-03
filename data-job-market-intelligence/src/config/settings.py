"""Central settings. Secret values are excluded from repr and loaded literally."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    app_env: str = "development"
    streamlit_api_url: str = "http://127.0.0.1:8000"
    database_url: SecretStr = SecretStr("")
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "job_market"
    db_user: str = "job_market"
    db_password: SecretStr = SecretStr("")
    db_sslmode: str = "prefer"
    db_schema: str = Field(default="djmi", pattern=r"^[a-z][a-z0-9_]*$")
    embedding_provider: Literal["local", "fastembed", "openai"] = "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=128, ge=8, le=2000)
    embedding_batch_size: int = Field(default=64, ge=1, le=256)
    llm_provider: Literal["extractive", "openai", "ollama"] = "extractive"
    openai_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_num_gpu: int | None = Field(default=None, ge=0)
    ollama_num_predict: int | None = Field(default=None, ge=32, le=4096)
    ollama_timeout_seconds: float = Field(default=120, ge=1, le=600)
    rag_retrieval_k: int = Field(default=20, ge=1, le=100)
    rag_rerank_k: int = Field(default=8, ge=1, le=100)
    rag_context_k: int = Field(default=6, ge=1, le=20)
    rag_similarity_threshold: float = Field(default=0.15, ge=0, le=1)
    rag_debug: bool = False
    rag_reranker: Literal["cross_encoder", "hybrid", "cosine"] = "hybrid"
    chunk_size: int = Field(default=450, ge=50, le=1200)
    chunk_overlap: int = Field(default=60, ge=0)
    v2_chunk_size: int = Field(default=320, ge=50, le=500)
    v2_chunk_overlap: int = Field(default=40, ge=0)
    prompt_version: Literal["v1", "v2"] = "v2"
    admin_token: SecretStr = SecretStr("")
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_sizes(self):
        if not self.rag_context_k <= self.rag_rerank_k <= self.rag_retrieval_k:
            raise ValueError("Require RAG_CONTEXT_K <= RAG_RERANK_K <= RAG_RETRIEVAL_K")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.v2_chunk_overlap >= self.v2_chunk_size:
            raise ValueError("V2_CHUNK_OVERLAP must be smaller than V2_CHUNK_SIZE")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    values = {**dotenv_values(PROJECT_ROOT / ".env", interpolate=False), **os.environ}
    return Settings(
        **{
            f: values[f.upper()]
            for f in Settings.model_fields
            if values.get(f.upper()) not in (None, "")
        }
    )
