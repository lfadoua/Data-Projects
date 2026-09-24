"""Connection factory with safe URL construction and an isolated schema."""

from functools import lru_cache

from sqlalchemy import URL, create_engine

from src.config.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    s = get_settings()
    url = s.database_url.get_secret_value() or URL.create(
        "postgresql+psycopg",
        username=s.db_user,
        password=s.db_password.get_secret_value(),
        host=s.db_host,
        port=s.db_port,
        database=s.db_name,
    )
    kwargs = {}
    if str(url).startswith("postgresql"):
        kwargs["connect_args"] = {
            "sslmode": s.db_sslmode,
            "connect_timeout": 10,
            "options": f"-csearch_path={s.db_schema},public,extensions -cstatement_timeout=120000",
        }
    return create_engine(url, pool_pre_ping=True, **kwargs)
