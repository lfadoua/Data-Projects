"""Validated HTTP API for analytics and grounded retrieval."""

import hmac
import json
import logging
from threading import Lock
from time import perf_counter
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies import database
from src.analytics.schemas import Answer, Filters, QueryRequest
from src.analytics.service import AnalyticsService
from src.config.logging_config import configure_logging
from src.config.settings import PROJECT_ROOT, get_settings
from src.database.models import IndexState, Job, JobChunk, JobChunkV2
from src.rag.indexing import reindex
from src.rag.service import answer_question
from src.routing.metadata import extract_metadata, merge_filters
from src.routing.service import ask

configure_logging()
log = logging.getLogger(__name__)
app = FastAPI(title="Data Job Market Intelligence", version="2.0.0")
index_lock = Lock()
DB = Annotated[object, Depends(database)]
FilterDependency = Annotated[Filters, Depends()]


class ReindexRequest(BaseModel):
    limit: int | None = Field(default=None, ge=3, le=100000)
    version: Literal["v1", "v2"] = "v1"


class HealthResponse(BaseModel):
    status: str
    database: str
    jobs: int
    chunks: int
    index_ready: bool


class ItemsResponse(BaseModel):
    total_jobs: int
    items: list[dict]


class JobsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[dict]


@app.middleware("http")
async def timing(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{perf_counter() - start:.3f}"
    log.info(
        "%s %s %s %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        perf_counter() - start,
    )
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    log.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Database unavailable or schema not initialized. Check "
                "configuration and initialize the database."
            )
        },
    )


@app.exception_handler(httpx.HTTPError)
async def provider_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Embedding provider unavailable. Check configuration or use local embeddings."
        },
    )


@app.exception_handler(ValueError)
async def configuration_error(request, exc):
    log.warning("Configuration/index error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                "Data or retrieval configuration is not ready. Run preprocessing "
                "and indexing, and verify provider settings."
            )
        },
    )


@app.exception_handler(FileNotFoundError)
async def missing_model(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Local embedding model file missing. Run indexing in this environment."},
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health(engine: DB):
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        jobs = connection.scalar(select(func.count()).select_from(Job))
        state_v2 = connection.scalar(select(IndexState.details).where(IndexState.id == 2))
        model = JobChunkV2 if state_v2 else JobChunk
        chunks = connection.scalar(select(func.count()).select_from(model))
        state = state_v2 or connection.scalar(select(IndexState.details).where(IndexState.id == 1))
    return {
        "status": "ok",
        "database": "connected",
        "jobs": jobs,
        "chunks": chunks,
        "index_ready": bool(state and chunks),
    }


@app.get("/api/analytics/overview", tags=["analytics"])
def overview(engine: DB, filters: FilterDependency) -> dict:
    return AnalyticsService(engine).overview(filters)


@app.get("/api/system/status", tags=["health"])
def system_status(engine: DB) -> dict:
    """Read-only index details for the UI; never expose connection configuration."""
    with engine.connect() as connection:
        state = connection.scalar(select(IndexState.details).where(IndexState.id == 2))
        version = "v2" if state else "v1"
        state = state or connection.scalar(select(IndexState.details).where(IndexState.id == 1))
        model = JobChunkV2 if version == "v2" else JobChunk
        chunks, embeddings = connection.execute(
            select(func.count(), func.count(model.embedding)).select_from(model)
        ).one()
    return {
        "index_version": version if state else None,
        "embeddings": embeddings,
        "chunks": chunks,
        "dimensions": state.get("dimensions") if state else None,
        "ready": bool(state and chunks and embeddings == chunks and not state.get("partial")),
        "partial": bool(state and state.get("partial")),
        "created_at": state.get("created_at") if state else None,
        "database": "PostgreSQL / pgvector" if engine.dialect.name == "postgresql" else "SQLite",
    }


@app.get("/api/analytics/skills", response_model=ItemsResponse, tags=["analytics"])
def skills(engine: DB, filters: FilterDependency, limit: int = Query(default=20, ge=1, le=100)):
    return AnalyticsService(engine).skills(filters, limit)


@app.get("/api/analytics/jobs", response_model=JobsResponse, tags=["analytics"])
def jobs(
    engine: DB,
    filters: FilterDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=200),
):
    return AnalyticsService(engine).jobs(filters, limit, offset, search)


@app.get("/api/analytics/filters", tags=["analytics"])
def facets(engine: DB) -> dict:
    return AnalyticsService(engine).facets()


@app.get("/api/analytics/skill-role", tags=["analytics"])
def skill_role(
    engine: DB,
    filters: FilterDependency,
    roles: str = Query(default="", max_length=500),
    skills: str = Query(default="", max_length=500),
) -> dict:
    return {
        "items": AnalyticsService(engine).skill_role(
            filters, [x for x in roles.split("|") if x], [x for x in skills.split("|") if x]
        )
    }


@app.get("/api/analytics/quality", tags=["analytics"])
def quality() -> dict:
    path = PROJECT_ROOT / "data/processed/quality_report.json"
    if not path.exists():
        raise HTTPException(404, "Run preprocessing to generate the quality report.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/assistant/query", response_model=Answer, tags=["assistant"])
def assistant(body: QueryRequest, engine: DB):
    result = ask(body, engine)
    log.info("Assistant route=%s", result.route)
    return result


@app.post("/api/rag/query", response_model=Answer, tags=["rag"])
def rag(body: QueryRequest, engine: DB):
    from src.routing.classifier import classify

    if classify(body.question).route == "analytics":
        raise HTTPException(422, "Use /api/assistant/query for numerical questions.")
    filters = merge_filters(
        extract_metadata(body.question, AnalyticsService(engine).facets()), body.filters
    )
    return answer_question(body.question, filters, engine)


@app.post("/api/rag/reindex", tags=["rag"])
def index(
    body: ReindexRequest, engine: DB, x_admin_token: str | None = Header(default=None)
) -> dict:
    expected = get_settings().admin_token.get_secret_value()
    if not expected:
        raise HTTPException(403, "HTTP reindexing disabled. Use CLI or configure ADMIN_TOKEN.")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(403, "Invalid administrator token.")
    if not index_lock.acquire(blocking=False):
        raise HTTPException(409, "Indexing is already running.")
    try:
        return reindex(engine, body.limit, body.version)
    finally:
        index_lock.release()
