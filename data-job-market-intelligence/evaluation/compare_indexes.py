"""Compare measured V1 and V2 results for the same five RAG questions."""

import argparse
import json
from pathlib import Path


def compare(v1_report, v2_report):
    v1 = {item["question"]: item for item in v1_report["questions"] if item["route"] == "rag"}
    v2 = {item["question"]: item for item in v2_report["questions"] if item["route"] == "rag"}
    if len(v1) != 5 or v1.keys() != v2.keys():
        raise ValueError("Both reports must contain the same five RAG questions")
    if any(item["traceability_issues"] for item in [*v1.values(), *v2.values()]):
        raise ValueError("Resolve source traceability issues before comparing indexes")
    if any(item["index_version"] != "v1" for item in v1.values()) or any(
        item["index_version"] != "v2" for item in v2.values()
    ):
        raise ValueError("Reports do not contain the requested index versions")

    rows = []
    for question, before in v1.items():
        after = v2[question]
        before_jobs = {source["job_id"] for source in before["sources"]}
        after_jobs = {source["job_id"] for source in after["sources"]}
        rows.append(
            {
                "question": question,
                "v1_retrieved_jobs": before["retrieved_jobs"],
                "v2_retrieved_jobs": after["retrieved_jobs"],
                "v1_retrieved_chunks": before["retrieved_chunks"],
                "v2_retrieved_chunks": after["retrieved_chunks"],
                "v1_cited_jobs": len(before_jobs),
                "v2_cited_jobs": len(after_jobs),
                "cited_job_overlap": len(before_jobs & after_jobs),
                "v1_latency_seconds": before["latency_seconds"],
                "v2_latency_seconds": after["latency_seconds"],
                "v1_evidence_quality": before["evidence_quality"],
                "v2_evidence_quality": after["evidence_quality"],
                "v1_cited_job_ids": sorted(before_jobs),
                "v2_cited_job_ids": sorted(after_jobs),
                "relevance_score": None,
                "note": "No labeled relevance judgments were collected.",
            }
        )
    return {
        "v1_recorded_at": v1_report["recorded_at"],
        "v2_recorded_at": v2_report["recorded_at"],
        "questions": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(
        json.loads(args.v1.read_text(encoding="utf-8")),
        json.loads(args.v2.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for item in result["questions"]:
        print(
            f"V1 {item['v1_retrieved_jobs']} jobs/{item['v1_latency_seconds']:.2f}s, "
            f"V2 {item['v2_retrieved_jobs']} jobs/{item['v2_latency_seconds']:.2f}s, "
            f"{item['cited_job_overlap']} cited jobs overlap | {item['question']}"
        )
