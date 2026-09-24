"""Record the ten requested live API questions without inventing quality metrics."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
QUESTIONS = [
    ("How many Data Engineer jobs are in France?", "analytics"),
    ("What are the most requested skills?", "analytics"),
    ("What are the top roles in the dataset?", "analytics"),
    ("Which locations contain the most jobs?", "analytics"),
    ("What skills are expected from Senior Data Engineers?", "rag"),
    ("What responsibilities do Data Engineers usually have?", "rag"),
    ("What technologies appear together with Kubernetes?", "rag"),
    ("What cloud technologies are commonly requested for Data Engineers?", "rag"),
    ("What should someone learn to prepare for Senior Data Engineering roles?", "rag"),
    ("How did salaries evolve month by month in 2025?", "analytics"),
]


def run(base_url):
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "api_url": base_url,
        "method": "Actual HTTP calls; observed problems require manual review.",
        "questions": [],
    }
    with httpx.Client(timeout=180) as client:
        health = client.get(base_url + "/health")
        health.raise_for_status()
        report["health"] = health.json()
        for question, expected in QUESTIONS:
            response = client.post(base_url + "/api/assistant/query", json={"question": question})
            response.raise_for_status()
            body = response.json()
            evidence = {hit["source_id"]: hit for hit in body["evidence"]}
            problems = []
            if body["route"] != expected:
                problems.append("Route differs from expected route.")
            if expected == "rag" and not body["sources"]:
                problems.append("No cited postings; inspect retrieval and synthesis.")
            for source in body["sources"]:
                hit = evidence.get(source["source_id"])
                if not hit or source["job_id"] != hit["job_id"]:
                    problems.append(f"Broken source linkage: {source['source_id']}.")
            if "salaries evolve" in question.lower() and not any(
                word in body["answer"].lower() for word in ("cannot", "unavailable", "no usable")
            ):
                problems.append("Salary answer needs manual unsupported-trend review.")
            report["questions"].append(
                {
                    "question": question,
                    "expected_route": expected,
                    "route": body["route"],
                    "answer": body["answer"],
                    "retrieved_postings": body["metadata"].get("retrieved_jobs", 0),
                    "evidence_quality": body["metadata"].get("evidence_quality"),
                    "index": body["metadata"].get("index"),
                    "sources": body["sources"],
                    "observed_problems": problems,
                    "manual_review": None,
                    "debug": body["metadata"].get("debug"),
                }
            )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "results" / "v2-ten-question-review.json"
    result = run(args.api_url.rstrip("/"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(result['questions'])} live answers to {output}")
    for item in result["questions"]:
        print(
            f"{item['route']:9} | {item['retrieved_postings']:2} retrieved | "
            f"{len(item['sources']):2} sources | {item['evidence_quality'] or '-':17} | "
            f"{item['question']}"
        )
