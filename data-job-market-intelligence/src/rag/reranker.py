"""Local candidate reranking. Cross-encoder logits are ranks, not probabilities."""

import re
from functools import lru_cache
from typing import Protocol

from src.config.settings import PROJECT_ROOT

STOP = set(
    (
        "what which how are the a an of for to in and do does is jobs job postings "
        "from with about usually have should someone learn prepare expected skills "
        "technologies data engineer engineers senior role roles"
    ).split()
)


class Reranker(Protocol):
    def rank(self, question: str, hits: list[dict], limit: int) -> list[dict]: ...


def words(value):
    return {w for w in re.findall(r"[a-z][a-z0-9+#.-]*", value.lower()) if w not in STOP}


class HybridReranker:
    """Free lexical relevance fused with vector score."""

    def rank(self, question, hits, limit):
        query = words(question)
        ranked = []
        for hit in hits:
            content = words(hit["chunk_text"])
            lexical = len(query & content) / len(query) if query else 0.0
            score = 0.55 * hit["similarity"] + 0.45 * lexical
            ranked.append({**hit, "rerank_score": round(score, 5), "rerank_method": "hybrid"})
        return sorted(ranked, key=lambda h: h["rerank_score"], reverse=True)[:limit]


@lru_cache(maxsize=1)
def cross_encoder():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(
        model_name="Xenova/ms-marco-MiniLM-L-6-v2",
        cache_dir=str(PROJECT_ROOT / "data/models/fastembed"),
        threads=4,
    )


class CrossEncoderReranker:
    def rank(self, question, hits, limit):
        if not hits:
            return []
        logits = list(cross_encoder().rerank(question, [h["chunk_text"] for h in hits]))
        if len(logits) != len(hits):
            raise ValueError("Reranker returned the wrong number of scores")
        ranked = [
            {**hit, "rerank_score": round(float(score), 5), "rerank_method": "cross_encoder"}
            for hit, score in zip(hits, logits, strict=True)
        ]
        return sorted(ranked, key=lambda h: h["rerank_score"], reverse=True)[:limit]


class DiverseCosineReranker:
    def rank(self, question, hits, limit):
        ranked = sorted(hits, key=lambda h: h["similarity"], reverse=True)
        return [
            {**h, "rerank_score": h["similarity"], "rerank_method": "cosine"}
            for h in ranked[:limit]
        ]


def select_distinct_jobs(hits, limit):
    selected, seen = [], set()
    for hit in hits:
        if hit["job_id"] not in seen:
            selected.append(hit)
            seen.add(hit["job_id"])
        if len(selected) >= limit:
            break
    return selected
