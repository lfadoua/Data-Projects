"""Grounded retrieval with a zero-cost extractive path and optional LLM synthesis."""

import hashlib
import json
import logging
import re
from collections import Counter
from contextlib import contextmanager
from time import perf_counter

from src.analytics.schemas import Answer
from src.config.settings import get_settings
from src.llm.client import get_client
from src.llm.structured_output import GeneratedAnswer, GeneratedSummary
from src.preprocessing.skill_extractor import extract_skills
from src.prompts.grounded_answer import get_prompt
from src.prompts.query_rewrite import rewrite
from src.prompts.selected_summary import SELECTED_SUMMARY_PROMPT
from src.rag.context_builder import build_context
from src.rag.grounding import (
    complete_quote_claims,
    extract_quotes,
    natural_supported_claims,
    verify_exact_claims,
)
from src.rag.reranker import (
    CrossEncoderReranker,
    DiverseCosineReranker,
    HybridReranker,
    select_distinct_jobs,
)
from src.rag.retriever import retrieve
from src.rag.synthesis import evidence_quality, excerpt, synthesize

log = logging.getLogger(__name__)
STOP = set(
    (
        "what which how are the a an of for to in and do does is jobs job "
        "postings expected from with about say responsibilities skills "
        "requirements commonly associated engineers engineer senior data"
    ).split()
)


def terms(text):
    return {
        w for w in re.findall(r"[a-z][a-z0-9+#.-]*", text.lower()) if w not in STOP and len(w) > 2
    }


def extractive_claims(question, evidence, version="v1"):
    query = terms(question)
    results = []
    for source in evidence:
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", source["chunk_text"])
            if len(s.strip()) >= 25
        ]
        scored = [(len(terms(s) & query), s) for s in sentences]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if scored:
            score, quote = scored[0]
            if query and score == 0:
                continue
            if version == "v2" and query and score / len(query) < 0.15:
                continue
            results.append({"text": quote, "source_id": source["source_id"], "quote": quote})
    return results


def verify_claims(claims, evidence):
    """Compatibility wrapper: IDs and literal quotes, never a semantic proof."""
    return verify_exact_claims(claims, evidence)


@contextmanager
def measured(timings, name):
    tick = perf_counter()
    try:
        yield
    finally:
        timings[name] = (timings.get(name) or 0) + (perf_counter() - tick) * 1000


INSUFFICIENT = "The retrieved job postings do not provide enough evidence to answer this reliably."


def answer_question(question, filters, engine, prompt_version=None, response_mode=None):
    """None retains the configured legacy path; explicit modes are request-local."""
    if response_mode not in (None, "extractive", "generative"):
        raise ValueError("Unsupported response mode")
    started = perf_counter()
    s = get_settings()
    version = prompt_version or s.prompt_version
    timings = {
        name: None
        for name in (
            "rewrite",
            "retrieval",
            "reranking",
            "context_building",
            "synthesis",
            "generation_preparation",
            "llm_generation",
            "citation_verification",
            "response_construction",
            "total",
        )
    }
    retrieval_timings = {}
    with measured(timings, "rewrite"):
        rewritten = rewrite(question)
    with measured(timings, "retrieval"):
        hits, index = retrieve(rewritten, filters, engine, timings=retrieval_timings)
    reranker = {
        "cross_encoder": CrossEncoderReranker,
        "hybrid": HybridReranker,
        "cosine": DiverseCosineReranker,
    }[s.rag_reranker]()
    warnings = []
    with measured(timings, "reranking"):
        try:
            ranked = reranker.rank(question, hits, s.rag_rerank_k)
        except Exception as exc:
            log.warning("Reranker failed (%s); using hybrid", type(exc).__name__)
            ranked = HybridReranker().rank(question, hits, s.rag_rerank_k)
            warnings.append("Local reranker unavailable; hybrid relevance was used.")
    with measured(timings, "context_building"):
        selected = select_distinct_jobs(ranked, s.rag_context_k)
        context, evidence = build_context(selected)

    mode, output_mode, strategy = "extractive", "extractive_quotes", "exact_quotes"
    usage = {}
    generation_prompt_hash = None
    generation_input_characters = None
    attempted = used_generation = False
    fallback_reason = None
    rejected = []
    with measured(timings, "synthesis"):
        quotes = extract_quotes(
            question, evidence, limit=2, prefer_compact=response_mode == "generative"
        )
        answer, points, claims = INSUFFICIENT, [], quotes
        legacy_synthesis = response_mode is None and s.llm_provider == "extractive"
        if legacy_synthesis:
            answer, points, claims = synthesize(question, evidence)
            output_mode, strategy = "extractive_synthesis", "legacy_synthesis"

    def fallback(reason, message):
        nonlocal mode, output_mode, strategy, fallback_reason, claims, used_generation
        mode, output_mode, strategy = "extractive_fallback", "extractive_quotes", "exact_quotes"
        fallback_reason = reason
        claims = quotes
        used_generation = False
        warnings.append(message)

    wants_generation = response_mode != "extractive" and s.llm_provider != "extractive"
    if response_mode == "generative" and s.llm_provider == "extractive":
        fallback(
            "provider_not_configured", "No generation provider is configured; using exact quotes."
        )
    elif wants_generation and evidence and quotes:
        attempted = True
        try:
            preparation_started = perf_counter()
            instructions = get_prompt(version)
            generation_context, schema = context, GeneratedAnswer
            if response_mode == "generative":
                # Quote provenance is assigned in Python, not regenerated token by token.
                # This path is explicit; the user's legacy strict contract remains unchanged.
                schema = GeneratedSummary
                generation_context = json.dumps(
                    [{"source_id": claim["source_id"], "text": claim["quote"]} for claim in quotes],
                    ensure_ascii=False,
                )
                instructions = SELECTED_SUMMARY_PROMPT
            # Selection and relevance checks already use the question. Keeping it
            # out of this narrow wording task avoids role-wide claims copied from it.
            generation_input = (
                f"Evidence JSON: {generation_context}"
                if response_mode == "generative"
                else f"Question: {question}\nEvidence JSON: {generation_context}"
            )
            generation_prompt_hash = hashlib.sha256(instructions.encode()).hexdigest()
            generation_input_characters = len(generation_input)
            timings["generation_preparation"] = (perf_counter() - preparation_started) * 1000
            with measured(timings, "llm_generation"):
                generated, usage = get_client().generate_structured(
                    instructions,
                    generation_input,
                    schema,
                )
            with measured(timings, "citation_verification"):
                candidates = generated.claims
                if response_mode == "generative":
                    supplied = {claim["source_id"]: claim["quote"] for claim in quotes}
                    candidates = [
                        {
                            "text": c.text,
                            "source_id": c.source_id,
                            "quote": supplied.get(c.source_id, ""),
                        }
                        for c in generated.claims
                    ]
                exact = verify_claims(candidates, evidence)
                rejected.extend(
                    {"reason": "invalid_source_or_quote"}
                    for _ in range(len(generated.claims) - len(exact))
                )
                if generated.insufficient_evidence:
                    claims = []
                    mode, used_generation = s.llm_provider, True
                elif response_mode == "generative":
                    claims, support_rejections = natural_supported_claims(exact, evidence, question)
                    rejected.extend(support_rejections)
                    if claims:
                        mode, used_generation = s.llm_provider, True
                        output_mode, strategy = "generated_synthesis", "conservative_paraphrase"
                    else:
                        fallback(
                            "unsupported_generated_claims",
                            "Generated claims did not pass conservative support checks; "
                            "using exact quotes.",
                        )
                else:
                    # Preserve the user's experimental strict output for omitted overrides.
                    claims = complete_quote_claims(exact, evidence)[:2]
                    if claims:
                        mode, used_generation = s.llm_provider, True
                        output_mode, strategy = "llm_selected_quotes", "legacy_strict_quotes"
                    else:
                        fallback(
                            "invalid_generated_citations",
                            "Generated citations could not be verified in context; "
                            "using exact quotes.",
                        )
        except Exception as exc:
            log.warning("LLM failed (%s); using exact local quotes", type(exc).__name__)
            usage = getattr(exc, "usage", usage)
            fallback(
                "generation_failed", "The generation provider failed; using exact local quotes."
            )
    elif wants_generation:
        # Retrieval without relevant evidence must not trigger an expensive generation call.
        claims = []

    with measured(timings, "citation_verification"):
        before = len(claims)
        if legacy_synthesis:
            # Different historical theme labels can legitimately cite the same
            # sentence. Preserve their contract while still checking each quote.
            claims = [valid for claim in claims for valid in verify_claims([claim], evidence)]
        else:
            claims = verify_claims(claims, evidence)
        if before != len(claims):
            rejected.extend({"reason": "final_quote_rejected"} for _ in range(before - len(claims)))
            legacy_synthesis = False
        if not legacy_synthesis or rejected:
            points = [f"{c['text']} [{c['source_id']}]" for c in claims]
            answer = "\n\n".join(points)
        if not claims:
            answer, points, output_mode = INSUFFICIENT, [], "insufficient_evidence"

    with measured(timings, "response_construction"):
        cited = {c["source_id"] for c in claims}
        supporting_quotes = {c["source_id"]: c["quote"] for c in claims}
        sources = [
            {
                "source_id": h["source_id"],
                "job_id": h["job_id"],
                "job_title": h["job_title"],
                "company": h["company"],
                "country": h["country"],
                "city": h["city"],
                "source_url": h["source_url"],
                "excerpt": supporting_quotes.get(h["source_id"], excerpt(h, question))[:320],
            }
            for h in evidence
            if h["source_id"] in cited
        ]
        counts = Counter(
            skill
            for h in evidence
            if h["source_id"] in cited
            for skill in extract_skills(h["chunk_text"])
        )
        cost = None
        if usage and s.input_cost_per_million is not None and s.output_cost_per_million is not None:
            cost = (
                (usage.get("input_tokens") or 0) * s.input_cost_per_million
                + (usage.get("output_tokens") or 0) * s.output_cost_per_million
            ) / 1_000_000
        metadata = {
            "mode": mode,
            "requested_mode": response_mode,
            "output_mode": output_mode,
            "generation_attempted": attempted,
            "generation_used": used_generation,
            "generation_prompt_sha256": generation_prompt_hash,
            "generation_input_characters": generation_input_characters,
            "fallback_reason": fallback_reason,
            "prompt_version": version,
            "prompt_variant": "selected_quote_summary"
            if response_mode == "generative"
            else "legacy",
            "filters": filters.model_dump(exclude_none=True),
            "rewritten_query": rewritten,
            "retrieved_jobs": len({h["job_id"] for h in evidence}),
            "cited_jobs": len({h["job_id"] for h in evidence if h["source_id"] in cited}),
            "insufficient_evidence": not bool(claims),
            "evidence_quality": evidence_quality(evidence, claims),
            "index": index,
            "claims": claims,
            "warning": " ".join(warnings) or None,
            "usage": usage,
            "estimated_cost_usd": cost,
            "timings_ms": timings,
            "retrieval_timings_ms": retrieval_timings,
            "reranker_requested": s.rag_reranker,
            "reranker_used": sorted({h["rerank_method"] for h in ranked}),
            "grounding": {
                "strategy": strategy,
                "source_ids_validated": True,
                "exact_quotes_validated": True,
                "semantic_entailment_verified": False,
                "rejected_claims": len(rejected),
                "rejection_reasons": sorted(
                    {r.get("reason", "support_rejected") for r in rejected}
                ),
            },
            "notice": (
                "A constrained generated answer from selected historical posting evidence."
                if output_mode == "generated_synthesis"
                else "Selected evidence from historical job postings; "
                "quotations are not market statistics."
            ),
            "evidence_note": (
                "Source and quote checks are deterministic. Natural-language support is restricted "
                "by conservative rules, not proven by a semantic entailment model."
            ),
        }
        if s.app_env == "development" and s.rag_debug:
            metadata["debug"] = {
                "question": question,
                "route": "rag",
                "rewritten_query": rewritten,
                "filters": filters.model_dump(exclude_none=True),
                "embedding_space": index["space"],
                "vector_retrieval": [
                    {
                        "chunk_id": h["chunk_id"],
                        "job_id": h["job_id"],
                        "similarity": h["similarity"],
                    }
                    for h in hits
                ],
                "reranking": [
                    {
                        "chunk_id": h["chunk_id"],
                        "job_id": h["job_id"],
                        "similarity": h["similarity"],
                        "score": h["rerank_score"],
                        "method": h["rerank_method"],
                    }
                    for h in ranked
                ],
                "selected_context": [h["source_id"] for h in evidence],
                "answer_source_ids": sorted(cited),
                "answer_mode": mode,
            }
        result = Answer(
            route="rag",
            answer=answer,
            key_points=points,
            sources=sources,
            evidence=evidence,
            skills=[{"name": name, "evidence_count": n} for name, n in counts.most_common(15)],
            metadata=metadata,
        )
    result.metadata["timings_ms"]["total"] = (perf_counter() - started) * 1000
    result.metadata["latency_seconds"] = round(result.metadata["timings_ms"]["total"] / 1000, 3)
    return result
