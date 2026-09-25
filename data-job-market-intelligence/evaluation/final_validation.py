"""Run the requested ten real questions and verify every RAG source in PostgreSQL."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_engine
from src.database.models import Job, JobChunk, JobChunkV2

QUESTIONS = [
    ("How many Data Engineer jobs are in France?", "analytics"),
    ("What are the top 10 most requested skills?", "analytics"),
    ("What percentage of jobs mention Python?", "analytics"),
    ("Which cities contain the most job postings?", "analytics"),
    ("What is the distribution of seniority levels?", "analytics"),
    ("What responsibilities are expected from Senior Data Engineers?", "rag"),
    ("What skills are commonly associated with Kubernetes?", "rag"),
    ("What AWS-related responsibilities appear in Data Engineer roles?", "rag"),
    ("What are common requirements for Machine Learning Engineer positions?", "rag"),
    ("What responsibilities appear in remote Data Analyst roles?", "rag"),
]


def check_sources(session, answer, expected_index):
    evidence = {item["source_id"]: item for item in answer["evidence"]}
    listed = {item["source_id"]: item for item in answer["sources"]}
    cited = set(re.findall(r"\[(S\d+)\]", answer["answer"]))
    issues = []
    if cited != set(listed):
        issues.append("Answer citation IDs and listed source IDs differ")
    chunk_model = JobChunkV2 if expected_index == "v2" else JobChunk
    for source_id, item in evidence.items():
        chunk = session.get(chunk_model, item["chunk_id"])
        job = session.get(Job, item["job_id"])
        if not chunk or not job:
            issues.append(f"{source_id}: missing database chunk or job")
            continue
        if chunk.job_id != job.id or chunk.chunk_text != item["chunk_text"]:
            issues.append(f"{source_id}: chunk does not match database record")
        if chunk.source_url != job.source_url:
            issues.append(f"{source_id}: chunk URL differs from original job")
    for source_id, item in listed.items():
        hit = evidence.get(source_id)
        job = session.get(Job, item["job_id"])
        if not hit or not job or hit["job_id"] != job.id or item["source_url"] != job.source_url:
            issues.append(f"{source_id}: listed source does not match original job")
    for claim in answer["metadata"].get("claims", []):
        hit = evidence.get(claim["source_id"])
        if not hit or claim["quote"] not in hit["chunk_text"]:
            issues.append(f"{claim['source_id']}: quoted claim is not in its retrieved chunk")
    return issues


def check_analytics(session, question, answer):
    """Reconcile each requested quantitative result with an independent SQL query."""
    data = answer["data"]
    if question == QUESTIONS[0][0]:
        actual = session.execute(
            text(
                "SELECT count(*) FROM jobs WHERE lower(normalized_job_title) = "
                "lower(:title) AND lower(country) = lower(:country)"
            ),
            {"title": "Data Engineer", "country": "France"},
        ).scalar_one()
        return {"total_jobs": actual}, [] if data["total_jobs"] == actual else [
            "France Data Engineer count differs from independent SQL"
        ]
    if question == QUESTIONS[1][0]:
        rows = session.execute(
            text(
                "SELECT skill, count(*) FROM job_skills GROUP BY skill "
                "ORDER BY count(*) DESC, skill LIMIT 10"
            )
        ).all()
        actual = [{"name": name, "count": count} for name, count in rows]
        observed = [{"name": x["name"], "count": x["count"]} for x in data["items"]]
        return {"top_skills": actual}, [] if observed == actual else [
            "Top ten skills differ from independent SQL"
        ]
    if question == QUESTIONS[2][0]:
        total = session.execute(text("SELECT count(*) FROM jobs")).scalar_one()
        count = session.execute(
            text("SELECT count(*) FROM job_skills WHERE lower(skill) = 'python'")
        ).scalar_one()
        actual = {"count": count, "total_jobs": total, "percentage": round(100 * count / total, 2)}
        observed = {key: data[key] for key in actual}
        return actual, [] if observed == actual else [
            "Python percentage differs from independent SQL"
        ]
    field = "city" if question == QUESTIONS[3][0] else "seniority"
    rows = session.execute(
        text(
            f"SELECT {field}, count(*) FROM jobs GROUP BY {field} "
            f"ORDER BY count(*) DESC, {field} LIMIT 10"
        )
    ).all()
    actual = [{"name": name or "Unknown", "count": count} for name, count in rows]
    observed = [{"name": x["name"], "count": x["count"]} for x in data["items"]]
    return {"group_by": field, "items": actual}, [] if observed == actual else [
        f"{field} distribution differs from independent SQL"
    ]


def run(base_url, expected_index):
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "expected_index": expected_index,
        "health": None,
        "questions": [],
    }
    with httpx.Client(timeout=180) as client, Session(get_engine()) as session:
        response = client.get(base_url + "/health")
        response.raise_for_status()
        report["health"] = response.json()
        for question, expected_route in QUESTIONS:
            started = perf_counter()
            response = client.post(base_url + "/api/assistant/query", json={"question": question})
            elapsed = round(perf_counter() - started, 3)
            response.raise_for_status()
            body = response.json()
            index = body["metadata"].get("index") or {}
            actual_index = index.get("version") or (
                "v1" if index.get("provider") == "local" else None
            )
            issues = []
            if body["route"] != expected_route:
                issues.append(f"Expected route {expected_route}, got {body['route']}")
            if expected_route == "rag":
                if actual_index != expected_index:
                    issues.append(f"Expected {expected_index} index, got {actual_index}")
                issues.extend(check_sources(session, body, expected_index))
                if not body["sources"]:
                    issues.append("No cited source")
                db_evidence = None
            else:
                db_evidence, analytics_issues = check_analytics(session, question, body)
                issues.extend(analytics_issues)
            report["questions"].append(
                {
                    "question": question,
                    "route": body["route"],
                    "filters": body["metadata"].get("filters", {}),
                    "answer": body["answer"],
                    "database_evidence": db_evidence,
                    "retrieved_jobs": body["metadata"].get("retrieved_jobs"),
                    "retrieved_chunks": len(body["evidence"]),
                    "source_ids": [source["source_id"] for source in body["sources"]],
                    "sources": body["sources"],
                    "claims": body["metadata"].get("claims", []),
                    "latency_seconds": elapsed,
                    "server_latency_seconds": body["metadata"].get("latency_seconds"),
                    "evidence_quality": body["metadata"].get("evidence_quality"),
                    "index_version": actual_index if expected_route == "rag" else None,
                    "grounding": (
                        "SQL over PostgreSQL" if body["route"] == "analytics" else "verified chunks"
                    ),
                    "traceability_issues": issues,
                }
            )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected-index", choices=("v1", "v2"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.api_url.rstrip("/"), args.expected_index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for item in result["questions"]:
        print(
            f"{item['route']:9} {item['latency_seconds']:6.2f}s "
            f"{len(item['source_ids']):2} sources "
            f"{len(item['traceability_issues']):2} issues | {item['question']}"
        )
    if result["health"]["jobs"] != 12217 or not result["health"]["index_ready"]:
        raise SystemExit("Health check did not confirm 12,217 jobs and a ready index")
    if any(item["traceability_issues"] for item in result["questions"]):
        raise SystemExit("Validation found route, index, or source-traceability issues")
