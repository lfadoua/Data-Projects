import pytest
from pydantic import ValidationError

from src.analytics.schemas import Filters, QueryRequest
from src.routing.classifier import classify
from src.routing.metadata import extract_metadata, merge_filters
from src.routing.service import ask


@pytest.mark.parametrize(
    "question,route",
    [
        ("How many Data Engineer jobs are in France?", "analytics"),
        ("What percentage of jobs mention Python?", "analytics"),
        ("What responsibilities are expected from Senior Data Engineers?", "rag"),
        ("What skills appear together with Kubernetes?", "rag"),
        ("Top 10 cloud technologies", "analytics"),
        ("Show salary distribution", "analytics"),
        ("Which city has the most Data Analyst positions?", "analytics"),
    ],
)
def test_router(question, route):
    assert classify(question).route == route


def test_metadata_explicit_filters_only():
    found = extract_metadata("Senior Data Engineers in France using Python")
    assert found.job_title == "Data Engineer"
    assert found.country == "France"
    assert found.seniority == "Senior"
    assert found.skill == "Python"
    assert extract_metadata("What should I learn?").country is None
    assert merge_filters(found, Filters(country="Canada")).country == "Canada"
    with pytest.raises(ValidationError):
        Filters(raw_sql="DELETE FROM jobs")


def test_routed_count_is_filtered(engine):
    result = ask(QueryRequest(question="How many Senior Data Engineer jobs are in France?"), engine)
    assert result.data["total_jobs"] == 1
    assert result.sources == []


def test_unrecognized_place_does_not_expand_to_global_count(engine):
    result = ask(QueryRequest(question="How many jobs are in Atlantis?"), engine)
    assert result.data == {"supported": False}


def test_question_skill_is_numerator_and_sidebar_skill_is_denominator(engine):
    result = ask(
        QueryRequest(
            question="What percentage of jobs mention Python?",
            filters=Filters(skill="SQL"),
        ),
        engine,
    )
    assert result.data["skill"] == "Python"
    assert result.data["percentage"] == 50


def test_missing_publication_dates_and_mixed_questions_clarify(engine):
    posted = ask(QueryRequest(question="How many jobs were posted in 2024?"), engine)
    assert posted.data["total_jobs"] == 1
    mixed = ask(
        QueryRequest(question="What are the top skills and responsibilities in these jobs?"),
        engine,
    )
    assert mixed.data == {"supported": False}


def test_requested_top_ten_and_full_distribution_are_in_answer(engine):
    skills = ask(QueryRequest(question="What are the top 10 most requested skills?"), engine)
    assert skills.route == "analytics"
    assert all(item["name"] in skills.answer for item in skills.data["items"])

    seniority = ask(QueryRequest(question="What is the distribution of seniority levels?"), engine)
    assert seniority.route == "analytics"
    assert seniority.answer.startswith("Distribution of seniority")
    assert all(item["name"] in seniority.answer for item in seniority.data["items"])
