"""Read-only live checks. Set RUN_DB_INTEGRATION=1 to opt in."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from api.main import app
from src.config.settings import get_settings
from src.database.connection import get_engine
from src.database.models import IndexState, Job, JobChunk, JobChunkV2

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.getenv("RUN_DB_INTEGRATION") != "1", reason="Live DB opt-in"),
]


def test_postgresql_vector_and_source_linkage():
    engine = get_engine()
    assert engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        jobs = connection.scalar(select(func.count()).select_from(Job))
        chunks = connection.scalar(select(func.count()).select_from(JobChunk))
        orphans = connection.scalar(
            select(func.count()).select_from(JobChunk).outerjoin(Job).where(Job.id.is_(None))
        )
        vector_dimension = connection.scalar(
            text("SELECT vector_dims(embedding) FROM job_chunks LIMIT 1")
        )
        cosine_index = connection.scalar(
            text(
                "SELECT count(*) FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = 'ix_chunks_embedding_cosine'"
            )
        )
    assert jobs > 0 and chunks >= jobs
    assert orphans == 0
    assert vector_dimension == get_settings().embedding_dimensions
    assert cosine_index == 1


def test_live_api_counts_and_real_citations():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200 and health.json()["index_ready"]
        count = client.get("/api/analytics/overview")
        assert count.status_code == 200
        assert count.json()["total_jobs"] == health.json()["jobs"]
        response = client.post(
            "/api/rag/query", json={"question": "What do postings say about Kubernetes?"}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["sources"]
        evidence = {hit["source_id"]: hit for hit in data["evidence"]}
        for claim in data["metadata"]["claims"]:
            assert claim["quote"] in evidence[claim["source_id"]]["chunk_text"]
        for source in data["sources"]:
            assert source["job_id"] == evidence[source["source_id"]]["job_id"]
            with Session(get_engine()) as session:
                original = session.get(Job, source["job_id"])
                assert original is not None
                assert source["source_url"] == original.source_url


def test_v2_index_is_complete_when_active():
    engine = get_engine()
    with engine.connect() as connection:
        state = connection.scalar(select(IndexState.details).where(IndexState.id == 2))
        if state is None:
            pytest.skip("V2 is not active yet")
        jobs = connection.scalar(select(func.count()).select_from(Job))
        chunks = connection.scalar(select(func.count()).select_from(JobChunkV2))
        orphans = connection.scalar(
            select(func.count()).select_from(JobChunkV2).outerjoin(Job).where(Job.id.is_(None))
        )
        dimensions = connection.scalar(
            text("SELECT vector_dims(embedding) FROM job_chunks_v2 LIMIT 1")
        )
        cosine_index = connection.scalar(
            text(
                "SELECT count(*) FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = 'ix_chunks_v2_embedding_cosine'"
            )
        )
    assert jobs == state["jobs"]
    assert chunks == state["chunks"]
    assert state["version"] == "v2" and not state["partial"]
    assert orphans == 0 and dimensions == 384 and cosine_index == 1
