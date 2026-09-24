"""Schema-adaptive CSV ingestion. Run python -m src.preprocessing.pipeline --load."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.config.settings import PROJECT_ROOT
from src.preprocessing.cleaner import clean_text
from src.preprocessing.normalizer import (
    normalize_employment,
    normalize_location,
    normalize_seniority,
    normalize_title,
    normalize_workplace,
    salary_number,
)
from src.preprocessing.skill_extractor import extract_skills

ALIASES = {
    "job_title": ["job_title", "title", "position"],
    "source_url": ["job_link", "source_url", "job_url", "url"],
    "description": ["job_summary", "description", "job_description", "summary"],
    "company": ["company", "company_name", "employer"],
    "location": ["job_location", "location"],
    "country": ["country", "country_name"],
    "city": ["city"],
    "level": ["job_level", "seniority", "experience_level"],
    "workplace": ["workplace_type", "workplace", "job_type"],
    "employment": ["employment_type", "contract_type"],
    "skills": ["job_skills", "skills"],
    "published_date": ["published_date", "date_posted", "posted_at"],
}


def value(row, field):
    return next(
        (
            str(row[k]).strip()
            for k in ALIASES.get(field, [field])
            if k in row and str(row[k]).strip()
        ),
        "",
    )


def load_sources(raw_dir: Path):
    frames = []
    profile = {}
    for path in sorted(raw_dir.glob("*.csv")):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
        profile[path.name] = {
            "rows": len(frame),
            "columns": list(frame.columns),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        frames.append((path, frame))
    candidates = [(p, f) for p, f in frames if set(ALIASES["job_title"]) & set(f.columns)]
    if len(candidates) != 1:
        raise ValueError(
            "Expected one postings CSV with a title column; found " + str(len(candidates))
        )
    source, main = candidates[0]
    for path, auxiliary in frames:
        if path == source:
            continue
        keys = [k for k in ALIASES["source_url"] if k in main and k in auxiliary]
        if not keys:
            continue
        key = keys[0]
        if auxiliary[key].duplicated().any():
            raise ValueError(f"Ambiguous duplicate join keys in {path.name}")
        extra = [c for c in auxiliary if c == key or c not in main.columns]
        main = main.merge(auxiliary[extra], how="left", on=key, validate="many_to_one").fillna("")
    if not set(ALIASES["description"]) & set(main.columns):
        raise ValueError("No description column found in postings or joined files")
    return main, profile


def process(raw_dir: Path, output_dir: Path) -> tuple[list[dict], dict]:
    frame, profile = load_sources(raw_dir)
    jobs, seen = [], set()
    duplicates = missing_title = invalid_salary = 0
    for row in frame.to_dict("records"):
        title = clean_text(value(row, "job_title"))
        if not title:
            missing_title += 1
            continue
        description = value(row, "description")
        cleaned = clean_text(description)
        url = value(row, "source_url") or None
        if url and not url.startswith(("https://", "http://")):
            url = None
        location = clean_text(value(row, "location")) or None
        company = clean_text(value(row, "company")) or None
        identity = url or "|".join((title, company or "", location or "", cleaned))
        job_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
        if job_id in seen:
            duplicates += 1
            continue
        seen.add(job_id)
        country, city = normalize_location(
            location or "", value(row, "country"), value(row, "city")
        )
        # search_country/search_city describe a search query, not a verified job location.
        low, high = (
            salary_number(row.get("salary_min", "")),
            salary_number(row.get("salary_max", "")),
        )
        if low and high and low > high:
            low = high = None
            invalid_salary += 1
        published = value(row, "published_date")
        try:
            published = date.fromisoformat(published[:10]).isoformat() if published else None
        except ValueError:
            published = None
        jobs.append(
            {
                "id": job_id,
                "job_title": title,
                "normalized_job_title": normalize_title(title),
                "company": company,
                "location": location,
                "country": country,
                "city": city,
                "seniority": normalize_seniority(title, value(row, "level")),
                "workplace_type": normalize_workplace(value(row, "workplace")),
                "employment_type": normalize_employment(value(row, "employment")),
                "salary_min": low,
                "salary_max": high,
                "salary_currency": row.get("salary_currency") or None,
                "salary_period": row.get("salary_period") or None,
                "description": description,
                "cleaned_description": cleaned,
                "skills": extract_skills(title + " " + cleaned + " " + value(row, "skills")),
                "source": "local_csv",
                "source_url": url,
                "published_date": published,
                "collected_date": row.get("first_seen") or None,
            }
        )
    total = len(jobs)
    report = {
        "source_files": profile,
        "raw_rows": len(frame),
        "processed_rows": total,
        "duplicates_removed": duplicates,
        "missing_title_removed": missing_title,
        "invalid_salary_ranges": invalid_salary,
        "date_note": "first_seen is collection coverage, not publication or market trend.",
        "country_note": "Search geography is not used as verified job geography.",
    }
    for field in ("location", "company", "cleaned_description", "country", "published_date"):
        report[f"missing_{field}_rate"] = sum(not j[field] for j in jobs) / total if total else None
    report["normalized_title_coverage"] = (
        sum(j["normalized_job_title"] != "Other / Unclassified" for j in jobs) / total
        if total
        else None
    )
    report["skill_extraction_coverage"] = (
        sum(bool(j["skills"]) for j in jobs) / total if total else None
    )
    dates = sorted(j["collected_date"] for j in jobs if j["collected_date"])
    report["collection_range"] = [dates[0], dates[-1]] if dates else None
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "jobs.jsonl").open("w", encoding="utf-8") as stream:
        for job in jobs:
            stream.write(json.dumps(job, ensure_ascii=False) + "\n")
    (output_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return jobs, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data/raw")
    parser.add_argument(
        "--load", action="store_true", help="Initialize PostgreSQL and load processed jobs"
    )
    args = parser.parse_args()
    jobs, report = process(args.raw_dir, PROJECT_ROOT / "data/processed")
    if args.load:
        from src.database.init_db import initialize
        from src.database.repositories import load_jobs

        engine = initialize()
        report["database_rows_loaded"] = load_jobs(engine, jobs)
    print(json.dumps({k: v for k, v in report.items() if k != "source_files"}, indent=2))


if __name__ == "__main__":
    main()
