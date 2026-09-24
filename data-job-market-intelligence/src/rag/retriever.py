"""Cosine pgvector search with SQL metadata filters and model-space checks."""

import logging
from functools import lru_cache

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.database.models import IndexState, Job, JobChunk, JobChunkV2
from src.database.repositories import apply_filters
from src.rag.embeddings import BGEEmbeddings, LocalEmbeddings, OpenAIEmbeddings

log = logging.getLogger(__name__)


@lru_cache(maxsize=3)
def local_provider(filename):
    return LocalEmbeddings.load(filename)


def retrieve(question, filters, engine):
    s = get_settings()
    with Session(engine) as session:
        state = session.get(IndexState, 2) if engine.dialect.name == "postgresql" else None
        state = state or session.get(IndexState, 1)
        if not state:
            raise ValueError("Retrieval index is missing. Run python -m src.rag.indexing.")
        details = state.details
        provider = (
            local_provider(details["model_file"])
            if details["provider"] == "local"
            else BGEEmbeddings()
            if details["provider"] == "fastembed"
            else OpenAIEmbeddings()
        )
        if provider.space != details["space"] or provider.dimensions != details["dimensions"]:
            raise ValueError(
                "Embedding configuration differs from the index. Reindex before querying."
            )
        vector = provider.embed_text(question)
        if not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
            return [], details
        model = JobChunkV2 if details["provider"] == "fastembed" else JobChunk
        query = (
            select(model)
            .join(Job, Job.id == model.job_id)
            .where(model.embedding_space == details["space"])
        )
        query = apply_filters(query, filters)
        if engine.dialect.name == "postgresql":
            distance = model.embedding.cosine_distance(vector)
            # Filter first, then exact ranking within the filtered set. This avoids
            # approximate HNSW post-filter starvation on small country/role slices.
            if filters.model_dump(exclude_none=True):
                from sqlalchemy import text

                session.execute(text("SET LOCAL enable_indexscan = off"))
            query = (
                query.add_columns(distance.label("distance"))
                .order_by(distance)
                .limit(s.rag_retrieval_k)
            )
            pairs = [(chunk, 1 - float(d)) for chunk, d in session.execute(query)]
        else:
            # SQLite is used only by offline tests; production uses pgvector above.
            pairs = []
            for chunk in session.scalars(query):
                v = np.asarray(chunk.embedding)
                score = (
                    float(np.dot(v, vector) / (np.linalg.norm(v) * np.linalg.norm(vector)))
                    if np.linalg.norm(v)
                    else 0
                )
                pairs.append((chunk, score))
            pairs.sort(key=lambda pair: pair[1], reverse=True)
            pairs = pairs[: s.rag_retrieval_k]
        hits = [
            {
                "chunk_id": c.chunk_id,
                "job_id": c.job_id,
                "chunk_text": c.chunk_text,
                "job_title": c.job_title,
                "company": c.company,
                "country": c.country,
                "city": c.city,
                "seniority": c.seniority,
                "source_url": c.source_url,
                "similarity": round(score, 5),
            }
            for c, score in pairs
            if score >= s.rag_similarity_threshold
        ]
        log.info("Retrieved %d chunks", len(hits))
        return hits, details
