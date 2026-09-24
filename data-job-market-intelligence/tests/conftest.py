"""Small controlled fixtures; never connect offline tests to the user's database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.config.settings import get_settings
from src.database.models import Base
from src.database.repositories import load_jobs


@pytest.fixture
def sample_jobs():
    descriptions = [
        (
            "Design Python data pipelines with SQL and Airflow. Maintain "
            "Kubernetes deployments and production reliability. Collaborate "
            "with engineering teams on cloud data infrastructure."
        ),
        (
            "Analyze business reports with SQL and Excel. Build Tableau "
            "dashboards for stakeholders. Explain data insights and "
            "communicate results to business leaders."
        ),
        (
            "Train machine learning models with Python and PyTorch. Evaluate "
            "predictive performance and monitor production systems. Research "
            "natural language processing algorithms."
        ),
        (
            "Manage AWS data platforms and Python services. Lead engineering "
            "teams and mentor colleagues. Automate Kubernetes infrastructure "
            "and production monitoring."
        ),
    ]
    jobs = []
    for i, description in enumerate(descriptions):
        jobs.append(
            {
                "id": str(i + 1),
                "job_title": [
                    "Senior Data Engineer",
                    "Data Analyst",
                    "Data Scientist",
                    "Lead Data Engineer",
                ][i],
                "normalized_job_title": [
                    "Data Engineer",
                    "Data Analyst",
                    "Data Scientist",
                    "Data Engineer",
                ][i],
                "company": ["A", "B", "C", "D"][i],
                "location": "Paris, France" if i < 2 else "New York, NY",
                "country": "France" if i < 2 else "United States",
                "city": "Paris" if i < 2 else "New York",
                "seniority": ["Senior", "Junior", "Unspecified", "Lead"][i],
                "workplace_type": ["Remote", "Onsite", "Hybrid", "Remote"][i],
                "employment_type": "Full-time",
                "salary_min": 50000 if i == 0 else None,
                "salary_max": 70000 if i == 0 else None,
                "salary_currency": "EUR" if i == 0 else None,
                "salary_period": "year" if i == 0 else None,
                "description": description,
                "cleaned_description": description,
                "skills": [
                    ["Python", "SQL", "Airflow", "Kubernetes"],
                    ["SQL", "Excel", "Tableau"],
                    ["Python", "PyTorch"],
                    ["Python", "AWS", "Kubernetes"],
                ][i],
                "source": "controlled_test_fixture",
                "source_url": f"https://example.org/test/{i}",
                "published_date": "2024-01-12" if i == 0 else None,
                "collected_date": "2024-01-17",
            }
        )
    return jobs


@pytest.fixture
def engine(sample_jobs):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    load_jobs(engine, sample_jobs)
    yield engine
    engine.dispose()


@pytest.fixture
def indexed(engine, monkeypatch, tmp_path):
    from src.rag import embeddings, indexing, retriever

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "extractive")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    monkeypatch.setenv("RAG_SIMILARITY_THRESHOLD", "0.05")
    get_settings.cache_clear()
    monkeypatch.setattr(indexing, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(embeddings, "PROJECT_ROOT", tmp_path)
    retriever.local_provider.cache_clear()
    indexing.reindex(engine)
    yield engine
    retriever.local_provider.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def client(indexed):
    from api.dependencies import database
    from api.main import app

    app.dependency_overrides[database] = lambda: indexed
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
