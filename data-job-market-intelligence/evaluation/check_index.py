"""Audit the active PostgreSQL/pgvector index without changing database state."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from src.database.connection import get_engine


def audit(version):
    if version not in {"v1", "v2"}:
        raise ValueError("version must be v1 or v2")
    state_id = 1 if version == "v1" else 2
    table = "job_chunks" if version == "v1" else "job_chunks_v2"
    index_name = (
        "ix_chunks_embedding_cosine" if version == "v1" else "ix_chunks_v2_embedding_cosine"
    )
    expected_dimensions = 128 if version == "v1" else 384
    with get_engine().connect() as connection:
        state = connection.execute(
            text("SELECT details FROM index_state WHERE id = :id"), {"id": state_id}
        ).scalar_one_or_none()
        result = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "state": state,
            "pgvector_extension": connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none(),
            "jobs": connection.execute(text("SELECT count(*) FROM jobs")).scalar_one(),
            "chunks": connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one(),
            "embeddings": connection.execute(
                text(f"SELECT count(embedding) FROM {table}")
            ).scalar_one(),
            "jobs_with_chunks": connection.execute(
                text(f"SELECT count(DISTINCT job_id) FROM {table}")
            ).scalar_one(),
            "orphan_chunks": connection.execute(
                text(
                    f"SELECT count(*) FROM {table} AS c "
                    "LEFT JOIN jobs AS j ON c.job_id = j.id WHERE j.id IS NULL"
                )
            ).scalar_one(),
            "dimension_counts": {
                str(dimensions): count
                for dimensions, count in connection.execute(
                    text(
                        f"SELECT vector_dims(embedding), count(*) FROM {table} "
                        "GROUP BY 1 ORDER BY 1"
                    )
                )
            },
            "zero_norm_embeddings": connection.execute(
                text(f"SELECT count(*) FROM {table} WHERE vector_norm(embedding) = 0")
            ).scalar_one(),
            "hnsw_cosine_index": bool(
                connection.execute(
                    text(
                        "SELECT 1 FROM pg_indexes WHERE schemaname = current_schema() "
                        "AND tablename = :table AND indexname = :index_name "
                        "AND indexdef LIKE '%USING hnsw%' "
                        "AND indexdef LIKE '%vector_cosine_ops%'"
                    ),
                    {"table": table, "index_name": index_name},
                ).scalar_one_or_none()
            ),
            "norm_range": connection.execute(
                text(
                    f"SELECT min(vector_norm(embedding)), max(vector_norm(embedding)) FROM {table}"
                )
            )
            .one()
            ._asdict(),
        }
    checks = {
        "state_exists": state is not None,
        "jobs_preserved": result["jobs"] == 12217,
        "extension_enabled": result["pgvector_extension"] is not None,
        "chunks_match_embeddings": result["chunks"] > 0
        and result["chunks"] == result["embeddings"],
        "all_jobs_have_chunks": result["jobs_with_chunks"] == result["jobs"],
        "no_orphans": result["orphan_chunks"] == 0,
        "dimensions_correct": result["dimension_counts"]
        == {str(expected_dimensions): result["chunks"]},
        "cosine_index_present": result["hnsw_cosine_index"],
        "norms_nonzero": result["zero_norm_embeddings"] == 0,
        "state_count_matches": state is not None
        and state.get("jobs") == result["jobs"]
        and state.get("chunks") == result["chunks"],
        "state_version_matches": state is not None
        and (state.get("version") == version or version == "v1" and "version" not in state),
        "full_index": state is not None and state.get("partial") is False,
    }
    result["checks"] = checks
    result["passed"] = all(checks.values())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v1", "v2"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.version)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)
