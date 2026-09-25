"""Behavioral checks for synthesis, relevance, and conservative filtering."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analytics.schemas import Filters
from src.database.models import IndexState, JobChunkV2
from src.prompts.query_rewrite import rewrite
from src.rag.indexing import iter_jobs
from src.rag.reranker import HybridReranker, select_distinct_jobs
from src.rag.synthesis import evidence_quality, synthesize
from src.routing.metadata import extract_metadata


def test_rewrite_preserves_role_and_intent():
    result = rewrite("Could you tell me what a Senior Data Engineer should know?")
    assert "Senior Data Engineer" in result
    assert "required skills qualifications" in result
    assert "France" not in result


def test_index_job_pages_keep_stable_order_and_limit(engine):
    assert [job.id for job in iter_jobs(engine, page_size=2)] == ["1", "2", "3", "4"]
    assert [job.id for job in iter_jobs(engine, limit=3, page_size=2)] == ["1", "2", "3"]


def test_metadata_does_not_invent_machine_learning_engineer():
    result = extract_metadata("What machine learning skills do Senior Data Engineers need?")
    assert result.job_title == "Data Engineer"
    assert result.seniority == "Senior"
    assert result.country is None and result.company is None


def test_hybrid_changes_order_and_keeps_distinct_jobs():
    hits = [
        {"job_id": "1", "similarity": 0.80, "chunk_text": "General office administration."},
        {"job_id": "2", "similarity": 0.62, "chunk_text": "Build Kubernetes deployment pipelines."},
        {"job_id": "2", "similarity": 0.60, "chunk_text": "Kubernetes infrastructure."},
    ]
    ranked = HybridReranker().rank("Kubernetes deployment pipelines", hits, 3)
    assert ranked[0]["job_id"] == "2"
    assert len(select_distinct_jobs(ranked, 3)) == 2
    assert all("rerank_score" in hit for hit in ranked)


def test_grounded_synthesis_cites_literal_skill_evidence():
    evidence = [
        {
            "source_id": "S1",
            "job_id": "1",
            "similarity": 0.7,
            "source_url": "https://example.org/1",
            "chunk_text": (
                "Build data pipelines with Python, SQL, and AWS. Maintain reliable data systems."
            ),
        },
        {
            "source_id": "S2",
            "job_id": "2",
            "similarity": 0.6,
            "source_url": "https://example.org/2",
            "chunk_text": (
                "Develop data pipelines using Python and SQL. Collaborate with engineers."
            ),
        },
    ]
    answer, points, claims = synthesize("What skills do Data Engineers need?", evidence)
    assert "Python" in answer and "SQL" in answer
    assert "[S1]" in answer and "[S2]" in answer
    assert "present in 2 selected posting(s) [S1], [S2]" in answer
    assert points and claims
    assert all(
        claim["quote"] in evidence[int(claim["source_id"][1:]) - 1]["chunk_text"]
        for claim in claims
    )
    assert evidence_quality(evidence, claims) == "Moderate evidence"


def test_synthesis_rejects_missing_anchor():
    evidence = [
        {
            "source_id": "S1",
            "job_id": "1",
            "similarity": 0.7,
            "source_url": None,
            "chunk_text": "Use Python and SQL to build reliable data pipelines for analysis.",
        }
    ]
    answer, _, claims = synthesize("What technologies appear together with Kubernetes?", evidence)
    assert "not provide enough" in answer
    assert not claims


def test_responsibility_synthesis_uses_question_topic_and_role_neutrally():
    evidence = [
        {
            "source_id": "S1",
            "job_id": "1",
            "similarity": 0.6,
            "source_url": "https://example.org/1",
            "chunk_text": (
                "Build AWS data pipelines for production. Maintain remote analyst reports."
            ),
        },
        {
            "source_id": "S2",
            "job_id": "2",
            "similarity": 0.6,
            "source_url": "https://example.org/2",
            "chunk_text": (
                "Deploy AWS cloud infrastructure for data services. Test analyst reports."
            ),
        },
    ]
    answer, _, claims = synthesize(
        "What AWS-related responsibilities appear in Data Engineer roles?", evidence
    )
    assert "AWS appears in responsibilities" in answer
    assert claims and all("AWS" in item["quote"] for item in claims)

    generic, _, _ = synthesize(
        "What responsibilities appear in remote Data Analyst roles?", evidence
    )
    assert "Data Engineer" not in generic


def test_debug_stages_are_development_only(indexed, monkeypatch):
    from src.config.settings import get_settings
    from src.rag import service

    current = get_settings()
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: current.model_copy(update={"app_env": "development", "rag_debug": True}),
    )
    development = service.answer_question("Describe Kubernetes deployments", Filters(), indexed)
    assert development.metadata["debug"]["route"] == "rag"
    assert development.metadata["debug"]["vector_retrieval"]
    assert development.metadata["debug"]["selected_context"]

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: current.model_copy(update={"app_env": "production", "rag_debug": True}),
    )
    production = service.answer_question("Describe Kubernetes deployments", Filters(), indexed)
    assert "debug" not in production.metadata


def test_interrupted_v2_build_resumes_without_activating_partial_index(
    engine, monkeypatch, tmp_path
):
    from src.config.settings import get_settings
    from src.rag import indexing

    settings = get_settings().model_copy(update={"embedding_batch_size": 1})
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    monkeypatch.setattr(indexing, "PROJECT_ROOT", tmp_path)

    class FakeBGE:
        space = "test-bge-384"
        dimensions = 384
        calls = 0
        fail_on_second = True

        def embed_documents(self, texts):
            self.calls += 1
            if self.calls == 2 and self.fail_on_second:
                raise RuntimeError("Simulated interrupted embedding")
            return [[1.0] + [0.0] * 383 for _ in texts]

    provider = FakeBGE()
    monkeypatch.setattr(indexing, "BGEEmbeddings", lambda: provider)
    with pytest.raises(RuntimeError, match="interrupted"):
        indexing.reindex(engine, version="v2")
    with Session(engine) as session:
        assert session.get(IndexState, 2) is None
        assert not session.scalars(select(JobChunkV2)).first()

    provider.fail_on_second = False
    details = indexing.reindex(engine, version="v2")
    assert details["resumed_chunks"] == 1
    assert details["chunks"] >= 4
    with Session(engine) as session:
        assert session.get(IndexState, 2).details == details
