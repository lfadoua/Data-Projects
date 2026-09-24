"""Run actual questions and save transparent metrics, never invented scores."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from time import perf_counter

from src.analytics.schemas import QueryRequest
from src.analytics.service import AnalyticsService
from src.config.settings import PROJECT_ROOT
from src.database.connection import get_engine
from src.rag.service import answer_question, terms
from src.routing.classifier import classify
from src.routing.metadata import extract_metadata, merge_filters
from src.routing.service import analytical_answer


def evaluate(engine, questions, version="v1"):
    service = AnalyticsService(engine)
    facets = service.facets()
    results = []
    for item in questions:
        started = perf_counter()
        request = QueryRequest(question=item["question"], filters=item.get("filters", {}))
        route = classify(request.question)
        filters = merge_filters(extract_metadata(request.question, facets), request.filters)
        metrics = {
            "id": item["id"],
            "question": request.question,
            "route": route.route,
            "routing_correct": route.route == item["expected_route"],
            "metadata_extraction_correct": all(
                filters.model_dump().get(k) == v
                for k, v in item.get("expected_metadata", {}).items()
            ),
            "prompt_version": version,
        }
        try:
            result = (
                analytical_answer(request.question, filters, service, request.filters)
                if route.route == "analytics"
                else answer_question(request.question, filters, engine, version)
            )
            evidence = result.evidence
            claims = result.metadata.get("claims", [])
            evidence_by_id = {h["source_id"]: h for h in evidence}
            valid = [c for c in claims if c["source_id"] in evidence_by_id]
            quotes = [
                c for c in valid if c["quote"] in evidence_by_id[c["source_id"]]["chunk_text"]
            ]
            relevant = set(item.get("relevant_job_ids", []))
            retrieved = {h["job_id"] for h in evidence}
            query_terms = terms(request.question)
            filter_values = filters.model_dump(exclude_none=True)
            checks = []
            for hit in evidence:
                # Verify filters against source rows instead of duplicated chunk labels.
                from sqlalchemy import select
                from sqlalchemy.orm import Session

                from src.database.models import Job
                from src.database.repositories import apply_filters

                with Session(engine) as session:
                    checks.append(
                        session.scalar(
                            apply_filters(
                                select(Job.id).where(Job.id == hit["job_id"]), filter_values
                            )
                        )
                        is not None
                    )
            metrics.update(
                {
                    "answer": result.answer,
                    "source_job_ids": [s["job_id"] for s in result.sources],
                    "recall_at_k": len(relevant & retrieved) / len(relevant) if relevant else None,
                    "recall_note": "No relevance labels"
                    if not relevant
                    else "Against supplied job-ID relevance labels",
                    "metadata_filter_correctness": mean(checks) if checks else None,
                    "retrieval_lexical_relevance_proxy": mean(
                        bool(terms(h["chunk_text"]) & query_terms) for h in evidence
                    )
                    if evidence and query_terms
                    else None,
                    "citation_correctness": len(valid) / len(claims) if claims else None,
                    "quote_grounding_proxy": len(quotes) / len(claims) if claims else None,
                    "unsupported_quote_rate": 1 - len(quotes) / len(claims) if claims else None,
                    "answer_lexical_relevance_proxy": len(terms(result.answer) & query_terms)
                    / len(query_terms)
                    if claims and query_terms
                    else None,
                    "semantic_groundedness_human": None,
                    "unsupported_claim_rate_human": None,
                    "insufficient_evidence": result.metadata.get("insufficient_evidence"),
                    "expected_abstention_correct": result.metadata.get("insufficient_evidence")
                    == item["expect_insufficient"]
                    if "expect_insufficient" in item
                    else None,
                    "token_usage": result.metadata.get("usage") or None,
                    "estimated_cost_usd": result.metadata.get("estimated_cost_usd"),
                    "error": None,
                }
            )
        except Exception as exc:
            metrics["error"] = type(exc).__name__
        metrics["latency_seconds"] = round(perf_counter() - started, 3)
        results.append(metrics)
    summary = {
        "questions": len(results),
        "routing_accuracy": mean(r["routing_correct"] for r in results),
        "successful_runs": sum(r["error"] is None for r in results),
        "mean_latency_seconds": mean(r["latency_seconds"] for r in results),
    }
    for metric in (
        "citation_correctness",
        "quote_grounding_proxy",
        "unsupported_quote_rate",
        "metadata_filter_correctness",
        "retrieval_lexical_relevance_proxy",
        "answer_lexical_relevance_proxy",
        "recall_at_k",
    ):
        values = [r[metric] for r in results if r.get(metric) is not None]
        summary[metric] = mean(values) if values else None
        summary[metric + "_scored_questions"] = len(values)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_version": version,
        "metric_warning": (
            "Lexical overlap and exact-quote checks are proxies, not semantic "
            "correctness or hallucination judgments. Human metrics require "
            "review."
        ),
        "summary": summary,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions", type=Path, default=PROJECT_ROOT / "evaluation/questions.json"
    )
    parser.add_argument("--versions", nargs="+", choices=["v1", "v2"], default=["v1"])
    args = parser.parse_args()
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    target = PROJECT_ROOT / "evaluation/results"
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for version in args.versions:
        result = evaluate(get_engine(), questions, version)
        path = target / f"{stamp}-{version}.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(version, json.dumps(result["summary"]))
        print("Saved", path)


if __name__ == "__main__":
    main()
