"""Focused, serial, read-only Qwen 1.5B validation; never downloads or reindexes.

Run: python -m evaluation.generative_validation --output evaluation/results/run.json
Existing baseline/legacy/extractive benchmarks do not need to be rerun.
"""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx

from evaluation.local_benchmark import (
    QUESTIONS,
    database_snapshot,
    free_memory_gib,
    run_case,
    save,
    source_snapshot,
    summarize,
    unload_models,
    utc_now,
)
from src.config.settings import get_settings
from src.database.connection import get_engine
from src.llm.client import OllamaClient
from src.rag import service


def generation_summary(cases):
    measured = [c for c in cases if not c["warmup"]]
    attempts = [c for c in measured if c.get("generation_attempted")]
    accepted = [
        c
        for c in attempts
        if c.get("generation_used")
        and c.get("mode") == "ollama"
        and c.get("output_mode") == "generated_synthesis"
        and c.get("claim_count", 0) > 0
    ]
    fallbacks = [c for c in attempts if c.get("mode") == "extractive_fallback"]
    return {
        "measured_cases": len(measured),
        "generation_attempts": len(attempts),
        "accepted_generated_responses": len(accepted),
        "accepted_responses_with_rejected_claims": sum(
            c.get("grounding", {}).get("rejected_claims", 0) > 0 for c in accepted
        ),
        "extractive_fallbacks": len(fallbacks),
        "accepted_rate_of_attempts": len(accepted) / len(attempts) if attempts else None,
        "fallback_rate_of_attempts": len(fallbacks) / len(attempts) if attempts else None,
        "no_generation_cases": len(measured) - len(attempts),
        "model_abstentions": sum(
            bool(c.get("insufficient_evidence") and c.get("generation_used")) for c in attempts
        ),
        "accepted_claims_with_attribution_or_inflection": sum(
            claim["text"].strip() != claim["quote"].strip()
            for c in accepted
            for claim in c.get("claims", [])
        ),
        "accepted_claims_still_verbatim": sum(
            claim["text"].strip() == claim["quote"].strip()
            for c in accepted
            for claim in c.get("claims", [])
        ),
        "fallback_reasons": dict(Counter(c.get("fallback_reason") for c in fallbacks)),
        "traceability_error_cases": sum(bool(c.get("traceability_issues")) for c in measured),
        "claim_count": sum(c.get("claim_count", 0) for c in measured),
        "semantic_entailment_measured": False,
    }


def run(output, repetitions):
    logging.disable(logging.CRITICAL)
    base = get_settings()
    url = base.ollama_url.rstrip("/")
    if urlsplit(url).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Only an existing loopback Ollama server is allowed")
    tags = httpx.get(url + "/api/tags", timeout=15)
    tags.raise_for_status()
    installed = {x["name"]: x for x in tags.json().get("models", [])}
    if "qwen2.5:1.5b" not in installed:
        raise ValueError("Install Qwen 1.5B yourself; this evaluation downloads nothing")
    version = httpx.get(url + "/api/version", timeout=15)
    version.raise_for_status()
    settings = base.model_copy(
        update={
            "llm_provider": "ollama",
            "llm_model": "qwen2.5:1.5b",
            "ollama_num_gpu": 0,
            "ollama_num_predict": 512,
            "rag_context_k": 2,
            "rag_retrieval_k": 20,
            "rag_rerank_k": 8,
            "rag_reranker": "hybrid",
            "rag_debug": False,
        }
    )
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        raise ValueError("Use the existing PostgreSQL database")
    report = {
        "recorded_at": utc_now(),
        "status": "running",
        "protocol": {
            "questions": QUESTIONS,
            "repetitions": repetitions,
            "warmup_excluded": True,
            "serial": True,
            "response_mode": "generative",
            "model": "qwen2.5:1.5b",
            "model_digest": installed["qwen2.5:1.5b"].get("digest"),
            "ollama_version": version.json().get("version"),
            "num_gpu": 0,
            "max_output_tokens": 512,
            "context_k": 2,
            "retrieval_k": 20,
            "rerank_k": 8,
            "reranker": "hybrid",
            "temperature": 0,
        },
        "source_sha256": source_snapshot(output.parent / (output.stem + "-source")),
        "database_before": database_snapshot(engine),
        "free_memory_gib": free_memory_gib(),
        "cases": [],
    }
    save(report, output)
    config = {"id": "qwen_1_5b_hybrid_natural", "response_mode": "generative"}
    schedule = [(0, QUESTIONS[0], True)] + [
        (r, q, False) for r in range(1, repetitions + 1) for q in QUESTIONS
    ]
    original = OllamaClient.generate_structured
    try:
        report["unloaded_before"] = unload_models(url)
        for repetition, question, warmup in schedule:
            diagnostics = {}

            def capture(client, instructions, content, schema):
                generated, usage = original(client, instructions, content, schema)
                diagnostics.update(
                    parsed=generated.model_dump(),
                    supplied=json.loads(content.partition("Evidence JSON: ")[2]),
                )
                return generated, usage

            with patch.object(OllamaClient, "generate_structured", capture):
                result = run_case(
                    engine, settings, config, question, repetition, warmup, service.get_prompt("v2")
                )
            # Fixed public job evidence only; no provider body, settings or credentials.
            result["generation_diagnostic"] = diagnostics
            report["cases"].append(result)
            report["summaries"] = summarize(report["cases"])
            report["generation_summary"] = generation_summary(report["cases"])
            save(report, output)
            print(
                f"{question['id']} {'warmup' if warmup else repetition}: "
                f"{result.get('mode')} {result['service_wall_seconds']:.3f}s",
                flush=True,
            )
        report["database_after"] = database_snapshot(engine)
        report["database_preserved"] = report["database_before"] == report["database_after"]
        report["status"] = "complete"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
    finally:
        try:
            report["unloaded_after"] = unload_models(url)
        except Exception as exc:
            report["unload_error_type"] = type(exc).__name__
        report["completed_at"] = utc_now()
        save(report, output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("Repetitions must be positive")
    if args.output.exists():
        parser.error("Output exists; select a new path to preserve prior measurements")
    try:
        result = run(args.output, args.repetitions)
        print("Validation", result["status"], flush=True)
        raise SystemExit(0 if result["status"] == "complete" else 1)
    except Exception as exc:
        print("Validation stopped:", type(exc).__name__, flush=True)
        raise SystemExit(1) from None
