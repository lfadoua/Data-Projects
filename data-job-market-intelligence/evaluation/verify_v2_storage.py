"""Compare every published V2 pgvector row with its saved computed vector."""

import argparse
import hashlib
import json
from itertools import islice
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import PROJECT_ROOT
from src.database.connection import get_engine
from src.database.models import IndexState, JobChunkV2


def verify(checkpoint_directory):
    files = sorted(checkpoint_directory.glob("batch-*.npy"))
    if not files:
        raise ValueError("No saved V2 embedding batches found")
    checked = 0
    max_abs_error = 0.0
    with Session(get_engine()) as session:
        state = session.get(IndexState, 2)
        if not state or state.details.get("version") != "v2" or state.details.get("partial"):
            raise ValueError("A complete V2 index is not active")
        records = iter(
            session.execute(
                select(
                    JobChunkV2.chunk_id,
                    JobChunkV2.job_id,
                    JobChunkV2.chunk_index,
                    JobChunkV2.chunk_text,
                    JobChunkV2.embedding,
                ).order_by(JobChunkV2.job_id, JobChunkV2.chunk_index)
            ).yield_per(64)
        )
        for file in files:
            expected = np.load(file, allow_pickle=False)
            if expected.ndim != 2 or expected.shape[1] != 384:
                raise ValueError(f"Invalid checkpoint shape: {file.name}")
            if file.stem != f"batch-{checked:06d}":
                raise ValueError(f"Noncontiguous checkpoint offset: {file.name}")
            rows = list(islice(records, len(expected)))
            if len(rows) != len(expected):
                raise ValueError("Fewer pgvector rows than saved embeddings")
            for row in rows:
                digest = hashlib.sha256(
                    f"{row.job_id}:{row.chunk_index}:{row.chunk_text}".encode()
                ).hexdigest()
                if row.chunk_id != digest:
                    raise ValueError(f"Chunk identity mismatch at row {checked}")
            stored = np.asarray([row.embedding for row in rows], dtype=np.float32)
            if stored.shape != expected.shape or not np.isfinite(stored).all():
                raise ValueError(f"Invalid stored vector batch: {file.name}")
            error = float(np.max(np.abs(stored - expected)))
            max_abs_error = max(max_abs_error, error)
            if error > 1e-6:
                raise ValueError(f"Stored embeddings differ from computed batch {file.name}")
            checked += len(expected)
        if next(records, None) is not None or checked != state.details["chunks"]:
            raise ValueError("Published V2 row count differs from saved embedding batches")
    return {
        "checkpoint_directory": str(checkpoint_directory),
        "batches_verified": len(files),
        "embeddings_verified": checked,
        "max_absolute_component_error": max_abs_error,
        "passed": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    directory = args.checkpoint_dir
    if directory is None:
        candidates = list((PROJECT_ROOT / "data/models/v2-checkpoints").iterdir())
        if len(candidates) != 1:
            raise SystemExit("Specify --checkpoint-dir when multiple checkpoint sets exist")
        directory = candidates[0]
    result = verify(directory)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
