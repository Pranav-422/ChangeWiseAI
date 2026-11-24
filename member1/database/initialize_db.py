"""Rebuild changewise.db from schema.sql and the synthetic CSVs. Safe to re-run.

Run from the member1 folder:  python -m database.initialize_db
"""
from pathlib import Path

from database.connection import DB_PATH, SCHEMA_PATH, get_connection
from engine.data_loader import SYNTHETIC_DIR, load_csv_data, load_data_to_db


def initialize_database(db_path: str | Path = DB_PATH, data_dir: str | Path = SYNTHETIC_DIR) -> dict[str, int]:
    """Drop and recreate the database, load all CSVs in one transaction, return row counts per table."""
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        load_data_to_db(conn, load_csv_data(data_dir))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


if __name__ == "__main__":
    counts = initialize_database()
    print(f"Initialized {DB_PATH.name} with {len(counts)} tables")
    for table, n in counts.items():
        print(f"  {table:22s} {n:4d} rows")
