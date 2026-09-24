"""Docker first-run bootstrap; existing data is preserved on later starts."""

from sqlalchemy import func, select

from src.config.settings import PROJECT_ROOT
from src.database.init_db import initialize
from src.database.models import IndexState, Job
from src.database.repositories import load_jobs
from src.preprocessing.pipeline import process
from src.rag.indexing import reindex


def main():
    engine = initialize()
    with engine.connect() as connection:
        count = connection.scalar(select(func.count()).select_from(Job))
        state = connection.scalar(select(IndexState.details).where(IndexState.id == 2))
    if not count:
        jobs, _ = process(PROJECT_ROOT / "data/raw", PROJECT_ROOT / "data/processed")
        load_jobs(engine, jobs)
    if not state:
        reindex(engine, version="v2")
    print("Database and retrieval index are ready.")


if __name__ == "__main__":
    main()
