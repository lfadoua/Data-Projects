"""Build embeddings and atomically replace the application's retrieval index."""

import argparse
import hashlib
import logging
import os
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import delete, insert, select, text
from sqlalchemy.orm import Session

from src.config.logging_config import configure_logging
from src.config.settings import PROJECT_ROOT, get_settings
from src.database.connection import get_engine
from src.database.init_db import initialize
from src.database.models import IndexState, Job, JobChunk, JobChunkV2
from src.rag.chunking import chunk_text
from src.rag.embeddings import BGEEmbeddings, LocalEmbeddings, OpenAIEmbeddings

log = logging.getLogger(__name__)


def checkpoint_dir(records, provider, size, overlap, batch_size):
    """Key persisted V2 batches to the exact model and source chunks."""
    digest = hashlib.sha256(f"{provider.space}:{size}:{overlap}:{batch_size}".encode())
    for record in records:
        digest.update(record["chunk_id"].encode())
    path = PROJECT_ROOT / "data/models/v2-checkpoints" / digest.hexdigest()
    path.mkdir(parents=True, exist_ok=True)
    return path


def checkpointed_vectors(provider, batch, path):
    """Reuse a complete local batch; publish new vectors by atomic file rename."""
    if path.is_file():
        try:
            cached = np.load(path, allow_pickle=False)
            if cached.shape == (len(batch), provider.dimensions) and np.isfinite(cached).all():
                return cached.tolist(), True
        except (OSError, ValueError):
            log.warning("Ignoring invalid embedding checkpoint %s", path.name)
    vectors = provider.embed_documents([record["chunk_text"] for record in batch])
    array = np.asarray(vectors, dtype=np.float32)
    if array.shape != (len(batch), provider.dimensions) or not np.isfinite(array).all():
        raise ValueError("Embedding provider returned invalid vectors")
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as output:
        np.save(output, array, allow_pickle=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    return array.tolist(), False


def reindex(engine, limit=None, version="v1"):
    if version not in ("v1", "v2"):
        raise ValueError("Unsupported index version")
    s = get_settings()
    if version == "v2":
        initialize(engine)
    size, overlap = (
        (s.v2_chunk_size, s.v2_chunk_overlap)
        if version == "v2"
        else (s.chunk_size, s.chunk_overlap)
    )
    with Session(engine) as session:
        query = select(Job).order_by(Job.id)
        if limit:
            query = query.limit(limit)
        jobs = list(session.scalars(query))
        records = []
        for job in jobs:
            for number, chunk in enumerate(chunk_text(job.cleaned_description, size, overlap)):
                records.append(
                    {
                        "chunk_id": hashlib.sha256(
                            f"{job.id}:{number}:{chunk}".encode()
                        ).hexdigest(),
                        "job_id": job.id,
                        "chunk_index": number,
                        "chunk_text": chunk,
                        "job_title": job.job_title,
                        "seniority": job.seniority,
                        "country": job.country,
                        "city": job.city,
                        "company": job.company,
                        "source_url": job.source_url,
                    }
                )
    if not records:
        raise ValueError("No descriptions to index. Run preprocessing with --load first.")
    log.info("Preparing %d chunks from %d jobs", len(records), len(jobs))
    documents = [r["chunk_text"] for r in records]
    model_file = None
    if version == "v2":
        provider = BGEEmbeddings()
    elif s.embedding_provider == "local":
        provider = LocalEmbeddings(s.embedding_dimensions).fit(documents)
        model_file = provider.save(PROJECT_ROOT / "data/models")
    elif s.embedding_provider == "openai":
        provider = OpenAIEmbeddings()
    else:
        raise ValueError("Use --v2 for FastEmbed BGE indexing")
    checkpoint = (
        checkpoint_dir(records, provider, size, overlap, s.embedding_batch_size)
        if version == "v2"
        else None
    )
    resumed = 0
    # Build fully before touching the active DB index; failed providers preserve it.
    for offset in range(0, len(records), s.embedding_batch_size):
        batch = records[offset : offset + s.embedding_batch_size]
        if checkpoint is not None:
            vectors, reused = checkpointed_vectors(
                provider, batch, checkpoint / f"batch-{offset:06d}.npy"
            )
            resumed += len(batch) if reused else 0
        else:
            vectors = provider.embed_documents([r["chunk_text"] for r in batch])
        for record, vector in zip(batch, vectors, strict=True):
            record.update(embedding=vector, embedding_space=provider.space)
        if version == "v2" and (offset // s.embedding_batch_size) % 25 == 0:
            log.info(
                "Embedded %d/%d chunks (%d resumed)",
                min(offset + len(batch), len(records)),
                len(records),
                resumed,
            )
    details = {
        "provider": "fastembed" if version == "v2" else s.embedding_provider,
        "space": provider.space,
        "model_file": model_file,
        "dimensions": provider.dimensions,
        "jobs": len(jobs),
        "chunks": len(records),
        "partial": limit is not None,
        "version": version,
        "chunk_size": size,
        "chunk_overlap": overlap,
        "resumed_chunks": resumed,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with engine.begin() as connection:
        # Serialize index swaps across API workers/processes.
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(722019)"))
        chunk_model = JobChunkV2 if version == "v2" else JobChunk
        state_id = 2 if version == "v2" else 1
        connection.execute(delete(chunk_model))
        connection.execute(delete(IndexState).where(IndexState.id == state_id))
        for offset in range(0, len(records), 200):
            connection.execute(insert(chunk_model), records[offset : offset + 200])
        connection.execute(insert(IndexState), {"id": state_id, "details": details})
        if engine.dialect.name == "postgresql":
            table = "job_chunks_v2" if version == "v2" else "job_chunks"
            index = (
                "ix_chunks_v2_embedding_cosine" if version == "v2" else "ix_chunks_embedding_cosine"
            )
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index} ON {table} "
                    "USING hnsw (embedding vector_cosine_ops)"
                )
            )
    log.info("Index activated: %d chunks", len(records))
    return details


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Explicit partial-index development run")
    parser.add_argument(
        "--v2", action="store_true", help="Build separate BGE index; keep V1 intact"
    )
    args = parser.parse_args()
    print(reindex(get_engine(), args.limit, "v2" if args.v2 else "v1"))
