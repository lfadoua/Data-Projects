"""Serial, read-only local RAG benchmark; run with python -m evaluation.local_benchmark.

Generation is restricted to a loopback Ollama server. No ingestion, indexing,
schema initialization, paid API calls, or application HTTP endpoints are used.
Baseline and optimized reports retain output semantics and source hashes so that
latency comparisons do not silently equate different kinds of answers.
"""

import argparse
import ctypes
import hashlib
import importlib
import importlib.util
import inspect
import json
import logging
import statistics
import sys
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from evaluation.final_validation import check_sources
from src.analytics.schemas import Filters
from src.config.settings import PROJECT_ROOT, get_settings
from src.database.connection import get_engine
from src.llm import client as llm_client
from src.rag import reranker, retriever, service

QUESTIONS = [
    {
        "id": "senior_de_responsibilities",
        "question": "What responsibilities are expected from Senior Data Engineers?",
        "filters": {"job_title": "Data Engineer", "seniority": "Senior"},
    },
    {
        "id": "aws_de_responsibilities",
        "question": "What AWS-related responsibilities appear in Data Engineer roles?",
        "filters": {"job_title": "Data Engineer"},
    },
    {
        "id": "kubernetes_skills",
        "question": "What skills are commonly associated with Kubernetes?",
        "filters": {},
    },
    {
        "id": "insufficient_evidence",
        "question": "What responsibilities are expected from Senior Data Engineers?",
        "filters": {
            "job_title": "Data Engineer",
            "seniority": "Senior",
            "company": "DJMI_NONEXISTENT_BENCHMARK_9F2A",
        },
    },
]
SOURCE_FILES = [
    "src/config/settings.py",
    "src/llm/client.py",
    "src/llm/structured_output.py",
    "src/prompts/grounded_answer.py",
    "src/prompts/verification.py",
    "src/prompts/selected_summary.py",
    "src/rag/service.py",
    "src/rag/grounding.py",
    "src/rag/retriever.py",
    "src/rag/reranker.py",
    "src/rag/context_builder.py",
    "src/rag/synthesis.py",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def free_memory_gib():
    """Measure available physical RAM on Windows without querying environment data."""
    if not hasattr(ctypes, "windll"):
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_pagefile", ctypes.c_ulonglong),
            ("available_pagefile", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.available_physical / 1024**3, 3)


def database_snapshot(engine):
    with Session(engine) as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        result = dict(
            session.execute(
                text(
                    "SELECT (SELECT count(*) FROM jobs) AS jobs, "
                    "(SELECT count(*) FROM job_chunks) AS v1_chunks, "
                    "(SELECT count(*) FROM job_chunks_v2) AS v2_chunks, "
                    "(SELECT count(embedding) FROM job_chunks_v2) AS v2_embeddings"
                )
            )
            .mappings()
            .one()
        )
        state = session.execute(text("SELECT details FROM index_state WHERE id=2")).scalar_one()
        missing_company = session.execute(
            text("SELECT count(*) FROM jobs WHERE lower(company)=lower(:company)"),
            {"company": QUESTIONS[-1]["filters"]["company"]},
        ).scalar_one()
    if result["jobs"] != 12217 or result["v2_chunks"] != 30955:
        raise ValueError("Unexpected corpus size; benchmark stopped without changing data")
    if (
        state.get("provider") != "fastembed"
        or state.get("version") != "v2"
        or state.get("dimensions") != 384
        or state.get("partial")
        or result["v2_embeddings"] != result["v2_chunks"]
        or missing_company
    ):
        raise ValueError("Expected complete local V2 index and absent benchmark company")
    result["index_state_sha256"] = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode()
    ).hexdigest()
    result["dimensions"] = state["dimensions"]
    result["insufficient_company_count"] = missing_company
    return result


def save(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def source_snapshot(directory, source_root=None):
    hashes = {}
    for relative in SOURCE_FILES:
        source = (source_root or PROJECT_ROOT) / relative
        if not source.exists():
            hashes[relative] = None  # A new module was absent in the preserved baseline.
            continue
        data = source.read_bytes()
        hashes[relative] = hashlib.sha256(data).hexdigest()
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return hashes


def load_baseline_snapshot(directory):
    """Run preserved pre-change code without replacing any working-tree file."""
    global service, retriever, llm_client
    for name in (
        "src.llm.structured_output",
        "src.prompts.grounded_answer",
        "src.llm.client",
        "src.rag.retriever",
        "src.rag.service",
    ):
        path = directory / (name.replace(".", "/") + ".py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        package, attribute = name.rsplit(".", 1)
        setattr(importlib.import_module(package), attribute, module)
        spec.loader.exec_module(module)
    service = sys.modules["src.rag.service"]
    retriever = sys.modules["src.rag.retriever"]
    llm_client = sys.modules["src.llm.client"]


def unload_models(base_url):
    """Unload, rather than kill, the one local model before changing configuration."""
    models = httpx.get(base_url + "/api/ps", timeout=15).json().get("models", [])
    names = [item.get("name") or item.get("model") for item in models]
    for name in names:
        response = httpx.post(
            base_url + "/api/generate", json={"model": name, "keep_alive": 0}, timeout=30
        )
        response.raise_for_status()
    deadline = perf_counter() + 30
    while True:
        active = httpx.get(base_url + "/api/ps", timeout=15).json().get("models", [])
        if not active:
            return names
        if perf_counter() >= deadline:
            raise RuntimeError("Local model did not unload; refusing simultaneous models")
        time.sleep(0.5)


class Instrumentation:
    """Wrap actual calls; nested timings are explicitly not additive."""

    def __init__(self, settings, frozen_prompt):
        self.settings = settings
        self.frozen_prompt = frozen_prompt
        self.timings = defaultdict(float)
        self.ollama_calls = []

    def timed(self, name, function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.timings[name] += (perf_counter() - started) * 1000

        return wrapped

    def enter(self, stack):
        for module in (service, retriever, llm_client):
            stack.enter_context(patch.object(module, "get_settings", lambda: self.settings))
        stack.enter_context(patch.object(service, "get_prompt", lambda *_: self.frozen_prompt))
        for name, attribute in (
            ("rewrite", "rewrite"),
            ("retrieval_embedding_and_sql", "retrieve"),
            ("selection", "select_distinct_jobs"),
            ("context_building", "build_context"),
            ("citation_verification", "verify_claims"),
            ("extractive_synthesis", "synthesize"),
            ("response_model_construction", "Answer"),
        ):
            stack.enter_context(
                patch.object(service, attribute, self.timed(name, getattr(service, attribute)))
            )
        for cls in (
            reranker.HybridReranker,
            reranker.CrossEncoderReranker,
            reranker.DiverseCosineReranker,
        ):
            stack.enter_context(patch.object(cls, "rank", self.timed("reranking", cls.rank)))
        stack.enter_context(
            patch.object(
                llm_client.OllamaClient,
                "generate_structured",
                self.timed("llm_generation_client", llm_client.OllamaClient.generate_structured),
            )
        )
        original_post = httpx.post

        def monitored_post(url, **kwargs):
            if url != self.settings.ollama_url.rstrip("/") + "/api/generate":
                raise RuntimeError("Benchmark blocks non-Ollama and paid generation requests")
            started = perf_counter()
            event = {}
            try:
                response = original_post(url, **kwargs)
                event["status_code"] = response.status_code
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                for key in (
                    "total_duration",
                    "load_duration",
                    "prompt_eval_duration",
                    "eval_duration",
                    "prompt_eval_count",
                    "eval_count",
                    "done_reason",
                ):
                    if key in body:
                        event[key] = body[key]
                return response
            except Exception as exc:
                event["exception_type"] = type(exc).__name__
                raise
            finally:
                event["client_wall_ms"] = round((perf_counter() - started) * 1000, 3)
                self.ollama_calls.append(event)

        stack.enter_context(patch.object(httpx, "post", monitored_post))


def run_case(engine, settings, config, case, repetition, warmup, frozen_prompt):
    measurement = Instrumentation(settings, frozen_prompt)
    arguments = {}
    response_mode = config.get("response_mode")
    if response_mode is not None:
        if "response_mode" not in inspect.signature(service.answer_question).parameters:
            raise ValueError("This service does not yet accept explicit response_mode")
        arguments["response_mode"] = response_mode
    result = {
        "recorded_at": utc_now(),
        "configuration": config["id"],
        "question_id": case["id"],
        "question": case["question"],
        "filters": case["filters"],
        "repetition": repetition,
        "warmup": warmup,
        "response_mode_argument": response_mode,
        "errors": [],
    }
    started = perf_counter()
    try:
        with ExitStack() as stack:
            measurement.enter(stack)
            answer = service.answer_question(
                case["question"], Filters(**case["filters"]), engine, **arguments
            )
        service_wall = perf_counter() - started
        serialization_started = perf_counter()
        body = answer.model_dump(mode="json")
        serialization_ms = (perf_counter() - serialization_started) * 1000
        validation_started = perf_counter()
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            issues = check_sources(session, body, "v2")
        validation_ms = (perf_counter() - validation_started) * 1000
        metadata = body["metadata"]
        claims = metadata.get("claims", [])
        evidence = {item["source_id"]: item for item in body["evidence"]}
        quote_match = all(
            item["source_id"] in evidence
            and item["quote"] in evidence[item["source_id"]]["chunk_text"]
            for item in claims
        )
        strict_match = all(item["text"].strip() == item["quote"].strip() for item in claims)
        if issues:
            result["errors"].append("PostgreSQL source or quote traceability failed")
        if case["id"] == "insufficient_evidence" and (
            claims or body["evidence"] or measurement.ollama_calls
        ):
            result["errors"].append("Absent-company case unexpectedly used evidence or Ollama")
        if metadata.get("mode") == "extractive_fallback":
            result["errors"].append("Generation fell back to extractive output")
        result.update(
            {
                "service_wall_seconds": round(service_wall, 6),
                "metadata_latency_seconds": metadata.get("latency_seconds"),
                "serialization_ms": round(serialization_ms, 3),
                "postgresql_validation_ms": round(validation_ms, 3),
                "answer": body["answer"],
                "claims": claims,
                "sources": [
                    {key: item[key] for key in ("source_id", "job_id", "job_title", "company")}
                    for item in body["sources"]
                ],
                "evidence_ids": [
                    {key: item[key] for key in ("source_id", "job_id", "chunk_id")}
                    for item in body["evidence"]
                ],
                "source_count": len(body["sources"]),
                "claim_count": len(claims),
                "retrieved_jobs": metadata.get("retrieved_jobs"),
                "mode": metadata.get("mode"),
                "response_mode": metadata.get("response_mode"),
                "output_mode": metadata.get("output_mode"),
                "insufficient_evidence": metadata.get("insufficient_evidence"),
                "evidence_quality_label": metadata.get("evidence_quality"),
                "warning": metadata.get("warning"),
                "fallback_reason": metadata.get("fallback_reason"),
                "generation_attempted": metadata.get("generation_attempted"),
                "generation_used": metadata.get("generation_used"),
                "grounding": metadata.get("grounding"),
                "usage": metadata.get("usage", {}),
                "quote_match": quote_match if claims else None,
                "strict_text_quote_match": strict_match if claims else None,
                "traceability_issues": issues,
                "index_version": metadata.get("index", {}).get("version"),
                "native_timings_ms": metadata.get("timings_ms"),
                "semantic_entailment_or_relevance_validated": False,
            }
        )
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
        result["service_wall_seconds"] = round(perf_counter() - started, 6)
    result["instrumented_timings_ms"] = {
        key: round(value, 3) for key, value in measurement.timings.items()
    }
    result["ollama_calls"] = measurement.ollama_calls
    result["ollama_called"] = bool(measurement.ollama_calls)
    result["wall_including_validation_seconds"] = round(perf_counter() - started, 6)
    result["passed_traceability_and_execution"] = not result["errors"]
    return result


def distribution(values):
    return (
        {"median": round(statistics.median(values), 6), "min": min(values), "max": max(values)}
        if values
        else None
    )


def summarize(cases):
    measured = [item for item in cases if not item["warmup"]]
    groups = defaultdict(list)
    for item in measured:
        groups[(item["configuration"], item["question_id"])].append(item)
    results = []
    for (configuration, question_id), items in groups.items():
        results.append(
            {
                "configuration": configuration,
                "question_id": question_id,
                "measured_repetitions": len(items),
                "service_wall_seconds": distribution([x["service_wall_seconds"] for x in items]),
                "wall_including_validation_seconds": distribution(
                    [x["wall_including_validation_seconds"] for x in items]
                ),
                "input_tokens": distribution(
                    [
                        x["usage"]["input_tokens"]
                        for x in items
                        if x.get("usage", {}).get("input_tokens") is not None
                    ]
                ),
                "output_tokens": distribution(
                    [
                        x["usage"]["output_tokens"]
                        for x in items
                        if x.get("usage", {}).get("output_tokens") is not None
                    ]
                ),
                "claim_counts": [x.get("claim_count") for x in items],
                "source_counts": [x.get("source_count") for x in items],
                "modes": dict(Counter(x.get("mode", "exception") for x in items)),
                "error_cases": sum(bool(x["errors"]) for x in items),
                "traceability_error_cases": sum(bool(x.get("traceability_issues")) for x in items),
                "ollama_call_count": sum(len(x["ollama_calls"]) for x in items),
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("baseline", "optimized"), required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--include-3b", choices=("auto", "no"), default="auto")
    parser.add_argument("--natural", action="store_true", help="Add one natural-synthesis config")
    parser.add_argument("--source-snapshot", type=Path, help="Preserved code for a baseline rerun")
    parser.add_argument("--max-output-tokens", type=int, default=512)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    if not 32 <= args.max_output_tokens <= 4096:
        parser.error("--max-output-tokens must be between 32 and 4096")
    if args.source_snapshot:
        if args.phase != "baseline":
            parser.error("--source-snapshot is only valid for baseline runs")
        load_baseline_snapshot(args.source_snapshot.resolve())
    logging.disable(logging.CRITICAL)
    output = args.output or (
        PROJECT_ROOT / "evaluation/results/rag-local-optimization" / f"{args.phase}-benchmark.json"
    )
    base_settings = get_settings()
    base_url = base_settings.ollama_url.rstrip("/")
    if urlsplit(base_url).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Benchmark requires a local loopback Ollama server")
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        raise ValueError("This benchmark requires the existing PostgreSQL corpus")
    frozen_prompt = service.get_prompt("v2")
    report = {
        "recorded_at": utc_now(),
        "phase": args.phase,
        "status": "running",
        "protocol": {
            "serial": True,
            "questions": QUESTIONS,
            "warmup": "One responsibilities question per configuration, excluded from summaries",
            "repetitions": args.repetitions,
            "context_k": 2,
            "retrieval_k": 20,
            "rerank_k": 8,
            "temperature": 0,
            "num_gpu": 0,
            "max_output_tokens": args.max_output_tokens if args.phase == "optimized" else None,
            "prompt_version": "v2",
            "prompt_sha256": hashlib.sha256(frozen_prompt.encode()).hexdigest(),
            "instrumentation": "Measured wrappers; nested stage timings are not additive",
            "validation_wall": "PostgreSQL validation and serialization reported separately",
            "output_semantics": (
                "Baseline retains existing legacy output, including experimental generated strict "
                "quote-only claims. Optimized LLM configurations use the same default/legacy "
                "response-mode argument. Explicit optimized extractive output may have different "
                "semantics; compare its claim/source counts and literal matching separately."
            ),
            "quality_limit": "Exact traceability is measured; relevance/entailment is not scored",
        },
        "source_sha256": source_snapshot(
            output.parent / f"{args.phase}-source", args.source_snapshot
        ),
        "database_before": database_snapshot(engine),
        "configurations": [],
        "cases": [],
        "summaries": [],
    }
    save(report, output)
    print(
        f"{args.phase.upper()}_PROCESS_IMPORTED; frozen modules/prompt; warmup starting", flush=True
    )
    tags_response = httpx.get(base_url + "/api/tags", timeout=15)
    tags_response.raise_for_status()
    installed = {
        item.get("name") or item.get("model") for item in tags_response.json().get("models", [])
    }
    configurations = [
        {"id": "extractive_hybrid", "provider": "extractive", "model": "", "reranker": "hybrid"},
        {
            "id": "qwen_1_5b_cross_encoder",
            "provider": "ollama",
            "model": "qwen2.5:1.5b",
            "reranker": "cross_encoder",
        },
        {
            "id": "qwen_1_5b_hybrid",
            "provider": "ollama",
            "model": "qwen2.5:1.5b",
            "reranker": "hybrid",
        },
        {
            "id": "qwen_3b_hybrid",
            "provider": "ollama",
            "model": "qwen2.5:3b",
            "reranker": "hybrid",
        },
    ]
    if args.phase == "optimized":
        configurations[0]["response_mode"] = "extractive"
    if args.natural:
        configurations.append(
            {
                "id": "qwen_1_5b_hybrid_natural",
                "provider": "ollama",
                "model": "qwen2.5:1.5b",
                "reranker": "hybrid",
                "response_mode": "generative",
            }
        )
    try:
        for config in configurations:
            config["unloaded_models_before"] = unload_models(base_url)
            config["free_physical_memory_gib_before_load"] = free_memory_gib()
            config["response_mode"] = config.get("response_mode")
            if config["id"] == "qwen_3b_hybrid" and (
                args.include_3b == "no"
                or config["free_physical_memory_gib_before_load"] is None
                or config["free_physical_memory_gib_before_load"] < 3
            ):
                config["status"] = "not_measured"
                config["reason"] = "3B disabled or available physical RAM below required 3 GiB"
                report["configurations"].append(config)
                save(report, output)
                print(f"{config['id']}: not measured; available RAM recorded", flush=True)
                continue
            if config["provider"] == "ollama" and config["model"] not in installed:
                config["status"] = "not_measured"
                config["reason"] = "Required local model is not installed; no download performed"
                report["configurations"].append(config)
                save(report, output)
                continue
            settings = base_settings.model_copy(
                update={
                    "llm_provider": config["provider"],
                    "llm_model": config["model"],
                    "ollama_num_gpu": 0,
                    "rag_context_k": 2,
                    "rag_retrieval_k": 20,
                    "rag_rerank_k": 8,
                    "rag_reranker": config["reranker"],
                    "prompt_version": "v2",
                    "rag_debug": False,
                    "ollama_num_predict": (
                        args.max_output_tokens if args.phase == "optimized" else None
                    ),
                }
            )
            config["applied_settings"] = {
                name: getattr(settings, name)
                for name in (
                    "llm_provider",
                    "llm_model",
                    "ollama_num_gpu",
                    "rag_context_k",
                    "rag_retrieval_k",
                    "rag_rerank_k",
                    "rag_reranker",
                    "rag_similarity_threshold",
                    "prompt_version",
                )
            }
            config["prompt_sha256"] = report["protocol"]["prompt_sha256"]
            config["applied_settings"].update(
                {
                    name: getattr(settings, name)
                    for name in type(settings).model_fields
                    if name.startswith("ollama_") and name != "ollama_url"
                }
            )
            config["status"] = "running"
            report["configurations"].append(config)
            schedule = [(0, QUESTIONS[0], True)] + [
                (repetition, case, False)
                for repetition in range(1, args.repetitions + 1)
                for case in QUESTIONS
            ]
            for repetition, case, warmup in schedule:
                print(
                    f"{config['id']} {'warmup' if warmup else f'rep {repetition}'} {case['id']}",
                    flush=True,
                )
                result = run_case(engine, settings, config, case, repetition, warmup, frozen_prompt)
                report["cases"].append(result)
                report["summaries"] = summarize(report["cases"])
                save(report, output)
                print(
                    f"  {result['service_wall_seconds']:.3f}s; "
                    f"{result.get('claim_count', 0)} claims; {len(result['errors'])} errors",
                    flush=True,
                )
            config["status"] = "measured"
            save(report, output)
        report["database_after"] = database_snapshot(engine)
        report["database_preserved"] = report["database_before"] == report["database_after"]
        report["status"] = "complete"
    except Exception as exc:
        report["status"] = "interrupted"
        report["exception_type"] = type(exc).__name__
        raise
    finally:
        try:
            report["unloaded_models_after"] = unload_models(base_url)
        except Exception as exc:
            report["unload_exception_type"] = type(exc).__name__
        report["completed_at"] = utc_now()
        report["summaries"] = summarize(report["cases"])
        save(report, output)
    print(f"Benchmark {report['status']}; {len(report['cases'])} cases saved", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Benchmark stopped: {type(error).__name__}; inspect saved progress", flush=True)
        sys.exit(1)
