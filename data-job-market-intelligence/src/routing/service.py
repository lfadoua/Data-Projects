"""Dispatch to deterministic analytics or retrieved-evidence answers."""

import re
from time import perf_counter

from src.analytics.schemas import Answer
from src.analytics.service import AnalyticsService
from src.preprocessing.skill_extractor import extract_skills
from src.routing.classifier import classify
from src.routing.metadata import extract_metadata, merge_filters

CLOUD_SKILLS = {
    "AWS",
    "Azure",
    "GCP",
    "BigQuery",
    "Redshift",
    "SageMaker",
    "Snowflake",
    "Databricks",
}


def analytical_answer(question, filters, service, explicit_filters=None):
    lower = question.lower()
    answer = "Calculated from the structured job database."
    active = filters.model_dump(exclude_none=True, exclude={"topic"})
    scope = ", ".join(str(v) for v in active.values()) or "all roles and locations"
    if re.search(r"\b(?:published|posted)\b", lower):
        if not service.trends()["items"]:
            return Answer(
                route="analytics",
                answer=(
                    "Publication dates are unavailable, so this dataset cannot "
                    "answer a posted-date question."
                ),
                data={"supported": False},
                metadata={
                    "filters": filters.model_dump(exclude_none=True),
                    "method": "clarification",
                },
            )
        date_match = re.search(r"\b20\d{2}(?:-(?:0[1-9]|1[0-2]))?\b", lower)
        date_prefix = date_match[0] if date_match else ""
        count = service.published_count(filters, date_prefix)
        return Answer(
            route="analytics",
            answer=f"{count:,} matching postings have a publication date"
            + (f" in {date_prefix}." if date_prefix else "."),
            data={"total_jobs": count, "date_prefix": date_prefix or None},
            metadata={"filters": filters.model_dump(exclude_none=True), "method": "SQL"},
        )
    if re.search(r"\b(?:top|most|percentage|how many)\b", lower) and re.search(
        r"\b(?:responsibilit|describe|duties)\w*\b", lower
    ):
        return Answer(
            route="analytics",
            answer=(
                "Please ask for the numerical ranking and the job-description "
                "evidence as separate questions."
            ),
            data={"supported": False},
            metadata={"filters": filters.model_dump(exclude_none=True), "method": "clarification"},
        )
    place = re.search(
        r"\b(?:jobs?|positions?|postings?)\s+(?:are\s+)?in\s+"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)",
        question,
    )
    if place and not (filters.country or filters.city or filters.company):
        return Answer(
            route="analytics",
            answer=(
                f"I could not identify '{place[1]}' as a job location. "
                "Select a country or city filter."
            ),
            data={"supported": False},
            metadata={"filters": filters.model_dump(exclude_none=True), "method": "clarification"},
        )
    requested_skills = extract_skills(question)
    if re.search(r"percentage|percent|proportion|frequency", lower) and len(requested_skills) > 1:
        data = {"supported": False}
        answer = "Please ask for the percentage of one skill at a time."
    elif re.search(r"percentage|percent|proportion|frequency", lower) and (
        requested_skills or filters.skill
    ):
        target_skill = requested_skills[0] if requested_skills else filters.skill
        denominator = filters.model_dump(exclude_none=True)
        if not explicit_filters or not explicit_filters.skill:
            denominator.pop("skill", None)
        data = service.skill_frequency(target_skill, denominator)
        answer = (
            f"{data['count']:,} of {data['total_jobs']:,} matching jobs "
            f"({data['percentage']}%) mention {data['skill']}."
        )
    elif "salary" in lower or "salaries" in lower:
        grouping = next(
            (
                field
                for terms, field in [
                    (("by seniority", "by level"), "seniority"),
                    (("by role", "by title"), "job_title"),
                    (("by country", "by location"), "country"),
                ]
                if any(term in lower for term in terms)
            ),
            None,
        )
        data = service.salary(filters, grouping)
        answer = (
            "Salary statistics grouped by currency and pay period."
            if data["groups"]
            else (
                "This historical dataset has no usable salaries with known currency and pay "
                "period; it cannot show month-by-month salary changes in 2025."
            )
        )
        if data["groups"] and re.search(r"\b(?:month|trend|evolv|2025)\b", lower):
            data = {"supported": False, "reason": "No comparable monthly salary time series."}
            answer = (
                "The dataset cannot support a month-by-month salary trend: comparable "
                "dated salary records are unavailable."
            )
    elif "trend" in lower or "month" in lower or "year" in lower:
        data = service.trends(filters)
        answer = (
            "Monthly counts from publication dates."
            if data["items"]
            else (
                "Publication dates are unavailable. Collection dates cannot "
                "establish a hiring trend."
            )
        )
    elif any(term in lower for term in ("top", "most", "distribution", "by ", "frequency")):
        field = next(
            (
                name
                for words, name in [
                    (("compan", "employer"), "company"),
                    (("cit", "location", "where"), "city"),
                    (("countr",), "country"),
                    (("seniority", "level"), "seniority"),
                    (("workplace", "remote", "hybrid", "onsite"), "workplace_type"),
                    (("role", "title", "famil"), "job_title"),
                ]
                if any(word in lower for word in words)
            ),
            None,
        )
        requested = re.search(r"\btop\s+(\d+)\b", lower)
        limit = min(int(requested[1]), 100) if requested else 10
        if "skill" in lower or "technolog" in lower or "cloud" in lower:
            data = service.skills(filters, 100 if "cloud" in lower else limit)
            if "cloud" in lower:
                data["items"] = [x for x in data["items"] if x["name"] in CLOUD_SKILLS][:limit]
            answer = (
                "Most requested skills in this historical dataset: "
                + "; ".join(
                    f"{x['name']} ({x['count']:,})"
                    for x in data["items"][: limit if requested else 5]
                )
                + ". Each job counts once per skill."
                if data["items"]
                else "No tracked skills match these filters."
            )
        elif field:
            data = {"group_by": field, "items": service.groups(field, filters, limit)}
            named = [
                item
                for item in data["items"]
                if item["name"] not in ("Unknown", "Other / Unclassified")
            ]
            missing = next(
                (
                    item
                    for item in data["items"]
                    if item["name"] in ("Unknown", "Other / Unclassified")
                ),
                None,
            )
            if field in ("city", "job_title") and named:
                heading = "recorded cities" if field == "city" else "classified roles"
                answer = (
                    f"Top {heading} among {scope}: "
                    + "; ".join(f"{item['name']} ({item['count']:,})" for item in named[:5])
                    + "."
                )
                if missing:
                    answer += f" {missing['count']:,} postings are {missing['name'].lower()}."
            elif data["items"]:
                shown = data["items"] if "distribution" in lower else data["items"][:5]
                heading = "Distribution of" if "distribution" in lower else "Top"
                answer = (
                    f"{heading} {field.replace('_', ' ')} values among {scope}: "
                    + "; ".join(f"{item['name']} ({item['count']:,})" for item in shown)
                    + "."
                )
            else:
                answer = f"No postings match {scope}."
        else:
            data = {"supported": False}
            answer = (
                "Please specify skills, job titles, seniority, countries, cities, "
                "companies, or workplace type."
            )
    elif re.search(r"how many|\bcount\b|\btotal\b|\bnumber of\b", lower):
        data = {"total_jobs": service.count(filters)}
        answer = f"{data['total_jobs']:,} postings in this historical dataset match {scope}."
    else:
        data = {"supported": False}
        answer = (
            "Please ask for a job count, skill percentage, top skills, "
            "distribution, salaries, or publication trend."
        )
    return Answer(
        route="analytics",
        answer=answer,
        data=data,
        metadata={
            "filters": filters.model_dump(exclude_none=True),
            "method": "SQL",
            "notice": "Calculated from the structured job database.",
        },
    )


def ask(request, engine):
    started = perf_counter()
    service = AnalyticsService(engine)
    filters = merge_filters(extract_metadata(request.question, service.facets()), request.filters)
    decision = classify(request.question)
    preparation_ms = (perf_counter() - started) * 1000
    if decision.route == "analytics":
        result = analytical_answer(request.question, filters, service, request.filters)
    else:
        from src.rag.service import answer_question

        result = answer_question(
            request.question, filters, engine, response_mode=request.response_mode
        )
    result.metadata["routing"] = decision.model_dump()
    result.metadata["request_preparation_ms"] = preparation_ms
    return result
