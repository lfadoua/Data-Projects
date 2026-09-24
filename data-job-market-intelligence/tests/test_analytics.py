import pytest
from sqlalchemy.exc import IntegrityError

from src.analytics.schemas import Filters
from src.analytics.service import AnalyticsService
from src.database.repositories import load_jobs


def test_sql_counts_and_skill_denominator(engine):
    service = AnalyticsService(engine)
    assert service.count() == 4
    assert service.count(Filters(country="France", job_title="Data Engineer")) == 1
    assert service.skill_frequency("Python")["percentage"] == 75
    assert service.skill_frequency("Python", Filters(country="France"))["percentage"] == 50
    assert service.skill_frequency("Python", Filters(skill="SQL"))["percentage"] == 50
    assert service.skills(Filters(country="France"))["items"][0]["name"] == "SQL"


def test_empty_pagination_and_injection(engine):
    service = AnalyticsService(engine)
    assert service.jobs(Filters(company="' OR 1=1 --"))["total"] == 0
    assert len(service.jobs(limit=1, offset=2)["items"]) == 1
    assert service.jobs(offset=100)["items"] == []


def test_salary_and_dates_are_explicit(engine):
    service = AnalyticsService(engine)
    assert service.salary()["groups"][0]["jobs"] == 1
    assert service.salary(group_by="seniority")["groups"][0]["seniority"] == "Senior"
    assert service.trends()["items"] == [{"month": "2024-01", "count": 1}]


def test_ingestion_rollback_and_repeatability(engine, sample_jobs):
    load_jobs(engine, sample_jobs)
    assert AnalyticsService(engine).count() == 4
    with pytest.raises(IntegrityError):
        load_jobs(engine, sample_jobs + [sample_jobs[0]])
    assert AnalyticsService(engine).count() == 4
