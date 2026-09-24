import json

import pandas as pd
import pytest

from src.preprocessing.cleaner import clean_text
from src.preprocessing.normalizer import (
    normalize_employment,
    normalize_location,
    normalize_seniority,
    normalize_title,
    normalize_workplace,
    salary_number,
)
from src.preprocessing.pipeline import process
from src.preprocessing.skill_extractor import extract_skills


def test_cleaning_preserves_paragraphs_and_removes_scripts():
    assert (
        clean_text("<p>Python &amp; SQL</p><script>bad()</script><p>Cloud</p>")
        == "Python & SQL\nCloud"
    )


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Sr. Data Engineer", "Data Engineer"),
        ("MLOps Engineer", "MLOps Engineer"),
        ("Lead Data Scientist", "Data Scientist"),
        ("Analytics Engineer", "Analytics Engineer"),
        ("Software Engineer", "Other / Unclassified"),
    ],
)
def test_titles(title, expected):
    assert normalize_title(title) == expected


@pytest.mark.parametrize(
    "title,level,expected",
    [
        ("Senior Data Engineer", "", "Senior"),
        ("Data Analyst", "Mid senior", "Mid/Senior (source)"),
        ("Data Intern", "", "Intern"),
        ("Principal Engineer", "", "Lead"),
    ],
)
def test_seniority(title, level, expected):
    assert normalize_seniority(title, level) == expected


def test_location_does_not_invent_geography():
    assert normalize_location("Paris, France") == ("France", "Paris")
    assert normalize_location("Boston, MA") == ("United States", "Boston")
    assert normalize_location("Remote") == (None, None)


def test_workplace_employment_salary():
    assert normalize_workplace("on-site") == "Onsite"
    assert normalize_employment("Remote") is None
    assert normalize_employment("full time") == "Full-time"
    assert salary_number("$120k") == 120000
    assert salary_number("competitive") is None


def test_skill_boundaries_and_aliases():
    assert extract_skills("Excel Pythonic gitlab") == ["Excel"]
    assert extract_skills("Python, SQL, Postgres and k8s") == [
        "Kubernetes",
        "PostgreSQL",
        "Python",
        "SQL",
    ]


def test_real_schema_join_duplicates_and_missing_fields(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(
        [
            {
                "job_link": "https://example.org/1",
                "job_title": "Data Engineer",
                "job_location": "",
                "first_seen": "2024-01-12",
                "search_country": "France",
            },
            {"job_link": "https://example.org/1", "job_title": "Data Engineer"},
            {"job_link": "https://example.org/2", "job_title": ""},
        ]
    ).fillna("").to_csv(raw / "posts.csv", index=False)
    pd.DataFrame(
        [{"job_link": "https://example.org/1", "job_summary": "Build Python pipelines."}]
    ).to_csv(raw / "summaries.csv", index=False)
    jobs, report = process(raw, tmp_path / "out")
    assert len(jobs) == 1
    assert jobs[0]["country"] is None
    assert jobs[0]["published_date"] is None
    assert jobs[0]["skills"] == ["Python"]
    assert report["duplicates_removed"] == 1
    assert report["missing_title_removed"] == 1
    assert json.loads((tmp_path / "out/quality_report.json").read_text())["processed_rows"] == 1
