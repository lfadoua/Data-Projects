from src.database.connection import get_engine


def database():
    return get_engine()
