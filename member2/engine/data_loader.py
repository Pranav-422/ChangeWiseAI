"""Read the shared planning dataset from SQLite (or JSON) into the input contract."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

LIST_TABLES = (
    "materials", "inventory", "demand", "purchase_orders", "suppliers",
    "supplier_materials", "purchasing_authorizations",
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_sqlite(path):
    """Expects one table per LIST_TABLES entry plus single-row `scenario` and `engineering_change`."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row

        def rows(table):
            return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]

        data = {table: rows(table) for table in LIST_TABLES}
        for single in ("scenario", "engineering_change"):
            found = rows(single)
            if len(found) != 1:
                raise ValueError(f"table {single} must hold exactly one row, found {len(found)}")
            data[single] = found[0]
    data.update(data.pop("scenario"))
    data.setdefault("validation_errors", [])
    return data
