"""Transactional ingestion and shared parameterized filter logic."""

from sqlalchemy import delete, exists, func, insert, select

from src.database.models import IndexState, Job, JobChunk, JobChunkV2, JobSkill

FILTER_COLUMNS = {
    "job_title": Job.normalized_job_title,
    "seniority": Job.seniority,
    "country": Job.country,
    "city": Job.city,
    "company": Job.company,
    "workplace_type": Job.workplace_type,
}


def apply_filters(statement, filters):
    values = filters.model_dump(exclude_none=True) if hasattr(filters, "model_dump") else filters
    for name, value in values.items():
        if not value:
            continue
        if name in FILTER_COLUMNS:
            statement = statement.where(func.lower(FILTER_COLUMNS[name]) == value.lower())
        elif name == "skill":
            statement = statement.where(
                exists(
                    select(JobSkill.job_id).where(
                        JobSkill.job_id == Job.id, func.lower(JobSkill.skill) == value.lower()
                    )
                )
            )
    return statement


def load_jobs(engine, jobs):
    if not jobs:
        raise ValueError("Refusing to replace database jobs with an empty input")
    # Only app-owned tables; rollback restores the old dataset if any insert fails.
    with engine.begin() as connection:
        for model in (JobChunkV2, JobChunk, IndexState, JobSkill, Job):
            connection.execute(delete(model))
        for offset in range(0, len(jobs), 300):
            batch = jobs[offset : offset + 300]
            connection.execute(insert(Job), batch)
            skills = [
                {"job_id": job["id"], "skill": skill} for job in batch for skill in job["skills"]
            ]
            if skills:
                connection.execute(insert(JobSkill), skills)
    return len(jobs)


def job_dict(job):
    return {column.name: getattr(job, column.name) for column in Job.__table__.columns}
