"""Assign citation IDs in code; source metadata never comes from a model."""

import json


def build_context(hits):
    evidence = [{**hit, "source_id": f"S{i}"} for i, hit in enumerate(hits, 1)]
    context = json.dumps(
        [
            {
                "source_id": h["source_id"],
                "job_title": h["job_title"],
                "company": h["company"],
                "country": h["country"],
                "city": h["city"],
                "text": h["chunk_text"],
            }
            for h in evidence
        ],
        ensure_ascii=False,
    )
    return context, evidence
