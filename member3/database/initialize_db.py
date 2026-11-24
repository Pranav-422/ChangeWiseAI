"""Create the application tables. Safe to run again: python -m member3.database.initialize_db"""
from pathlib import Path

SCHEMA = Path(__file__).with_name("app_schema.sql")


def initialize(connection):
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))


if __name__ == "__main__":
    from .connection import transaction
    with transaction():
        pass
    print("Application database is ready.")
