"""Grounded retrieval with a zero-cost extractive path and optional LLM synthesis."""

import logging
import re
from collections import Counter
from time import perf_counter

from src.analytics.schemas import Answer
from src.config.settings import get_settings
from src.llm.client import get_client
from src.llm.structured_output import GeneratedAnswer
from src.preprocessing.skill_extractor import extract_skills
from src.prompts.grounded_answer import get_prompt
from src.prompts.query_rewrite import rewrite
from src.rag.context_builder import build_context
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
    lookup = {s["source_id"]: s for s in evidence}
    accepted = []
    for claim in claims:
        item = claim.model_dump() if hasattr(claim, "model_dump") else claim
        source = lookup.get(item["source_id"])
        quote = item["quote"].strip()
        if source and len(quote) >= 20 and quote in source["chunk_text"]:
            # Exact quotes guarantee traceability; paraphrase truth still needs human evaluation.
            accepted.append(item)
    return accepted


def answer_question(question, filters, engine, prompt_version=None):
    started = perf_counter()
    s = get_settings()
    version = prompt_version or s.prompt_version
    rewritten = rewrite(question)
    hits, index = retrieve(rewritten, filters, engine)
    reranker = {
        "cross_encoder": CrossEncoderReranker,
        "hybrid": HybridReranker,
        "cosine": DiverseCosineReranker,
    }[s.rag_reranker]()
    rerank_warning = None
    try:
        ranked = reranker.rank(question, hits, s.rag_rerank_k)
    except Exception as exc:
        log.warning("Reranker failed (%s); using hybrid", type(exc).__name__)
        ranked = HybridReranker().rank(question, hits, s.rag_rerank_k)
        rerank_warning = "Local reranker unavailable; hybrid relevance was used."
    selected = select_distinct_jobs(ranked, s.rag_context_k)
    context, evidence = build_context(selected)
    mode, usage, warning = s.llm_provider, {}, rerank_warning
    answer, points, claims = synthesize(question, evidence)
    if evidence and s.llm_provider != "extractive":
        try:
            generated, usage = get_client().generate_structured(
                get_prompt(version),
                f"Question: {question}\nEvidence JSON: {context}",
                GeneratedAnswer,
            )
            generated_claims = (
                [] if generated.insufficient_evidence else verify_claims(generated.claims, evidence)
            )
            if generated_claims:
                claims = generated_claims
                points = [f"{c['text']} [{c['source_id']}]" for c in claims]
                answer = "\n\n".join(points)
            elif generated.insufficient_evidence:
                claims, points = [], []
                answer = (
                    "The retrieved postings do not provide enough evidence to answer this reliably."
                )
        except Exception as exc:
            log.warning("LLM failed (%s); using deterministic synthesis", type(exc).__name__)
            mode = "extractive_fallback"
            warning = (
                "The generation provider is unavailable; using evidence-based local synthesis."
            )
    claims = verify_claims(claims, evidence)
    used = {c["source_id"] for c in claims}
    used.update(re.findall(r"\[(S\d+)\]", " ".join(points)))
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
        if h["source_id"] in used
    ]
    counts = Counter(
        skill
        for h in evidence
        if h["source_id"] in used
        for skill in extract_skills(h["chunk_text"])
    )
    if not claims:
        points = []
        answer = (
            "The retrieved job postings do not provide enough evidence to answer this reliably."
        )
    cost = None
    if usage and s.input_cost_per_million is not None and s.output_cost_per_million is not None:
        cost = (
            (usage.get("input_tokens") or 0) * s.input_cost_per_million
            + (usage.get("output_tokens") or 0) * s.output_cost_per_million
        ) / 1_000_000
    metadata = {
        "mode": mode,
        "prompt_version": version,
        "filters": filters.model_dump(exclude_none=True),
        "rewritten_query": rewritten,
        "retrieved_jobs": len({h["job_id"] for h in evidence}),
        "cited_jobs": len({h["job_id"] for h in evidence if h["source_id"] in used}),
        "insufficient_evidence": not bool(claims),
        "evidence_quality": evidence_quality(evidence, claims),
        "index": index,
        "claims": claims,
        "warning": warning,
        "usage": usage,
        "estimated_cost_usd": cost,
        "latency_seconds": round(perf_counter() - started, 3),
        "notice": "Generated from retrieved job posting evidence.",
        "evidence_note": (
            "Retrieved examples are not population statistics. Quote verification does not "
            "prove paraphrase entailment."
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
                {"chunk_id": h["chunk_id"], "job_id": h["job_id"], "similarity": h["similarity"]}
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
            "answer_source_ids": sorted(used),
            "answer_mode": mode,
        }
    return Answer(
        route="rag",
        answer=answer,
        key_points=points,
        sources=sources,
        evidence=evidence,
        skills=[{"name": name, "evidence_count": n} for name, n in counts.most_common(15)],
        metadata=metadata,
    )
