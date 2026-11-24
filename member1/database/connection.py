"""SQLite connection helper. No credentials: SQLite is a local file."""
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "changewise.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")   # SQLite leaves FK enforcement off unless asked per connection
    conn.row_factory = sqlite3.Row
    return conn
