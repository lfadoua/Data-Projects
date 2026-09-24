"""Conservative exact phrase extraction with optional database vocabulary."""

import re

from src.analytics.schemas import Filters
from src.preprocessing.normalizer import COUNTRIES
from src.preprocessing.skill_extractor import extract_skills


def phrase_present(phrase, question):
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", question, re.I))


def extract_metadata(question: str, facets: dict | None = None) -> Filters:
    data = {}
    # Occupational phrases only: "machine learning" as a skill must not turn
    # an explicit Data Engineer question into Machine Learning Engineer.
    roles = [
        ("MLOps Engineer", r"\bml\s?ops engineers?\b"),
        ("Machine Learning Engineer", r"\bmachine learning engineers?\b|\bml engineers?\b"),
        ("Analytics Engineer", r"\banalytics engineers?\b"),
        ("Data Engineer", r"\bdata engineers?\b|\bdata engineering roles?\b"),
        ("Data Scientist", r"\bdata scientists?\b"),
        ("Data Architect", r"\bdata architects?\b"),
        ("BI Analyst", r"\bbi analysts?\b|\bbusiness intelligence analysts?\b"),
        ("Data Analyst", r"\bdata analysts?\b"),
        ("AI Engineer", r"\bai engineers?\b"),
    ]
    for role, pattern in roles:
        if re.search(pattern, question, re.I):
            data["job_title"] = role
            break
    for field, choices in {
        "seniority": ["Senior", "Junior", "Intern", "Lead", "Executive"],
        "workplace_type": ["Remote", "Hybrid", "Onsite"],
        "country": list(set(COUNTRIES.values()))
        + ["Spain", "Italy", "Brazil", "Morocco", "Japan", "Netherlands", "Ireland", "Singapore"],
    }.items():
        matches = [c for c in choices if phrase_present(c, question)]
        if len(matches) == 1:
            data[field] = matches[0]
    for alias, country in [("USA", "United States"), ("UK", "United Kingdom")]:
        if phrase_present(alias, question):
            data["country"] = country
    for field in ("city", "company", "country"):
        matches = [
            v for v in (facets or {}).get(field, []) if len(v) > 2 and phrase_present(v, question)
        ]
        if field == "company":
            matches = [
                value
                for value in matches
                if re.search(
                    r"\b(?:at|for|from|company|employer)\s+" + re.escape(value) + r"\b",
                    question,
                    re.I,
                )
            ]
        if matches:
            # A single longest explicit phrase avoids partial city/company names.
            data[field] = max(matches, key=len)
    skills = extract_skills(question)
    if len(skills) == 1:
        data["skill"] = skills[0]
    if re.search(r"\bcloud\b", question, re.I):
        data["topic"] = "cloud"
    return Filters(**data)


def merge_filters(inferred: Filters, explicit: Filters) -> Filters:
    return Filters(
        **{**inferred.model_dump(exclude_none=True), **explicit.model_dump(exclude_none=True)}
    )
