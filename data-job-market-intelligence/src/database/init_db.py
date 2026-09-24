"""Idempotently initialize only this application's schema."""

from sqlalchemy import text

from src.config.settings import get_settings
from src.database.connection import get_engine
from src.database.models import Base


def initialize(engine=None):
    engine = engine or get_engine()
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            schema = get_settings().db_schema  # Validated identifier, never user SQL.
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(connection)
    return engine


if __name__ == "__main__":
    initialize()
    print("Application schema initialized.")
