"""Load the eight input tables from CSV or SQLite, and persist simulation runs and exceptions."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import ROOT

SYNTHETIC_DIR = ROOT / "data" / "synthetic"
# Insert order respects foreign keys.
INPUT_TABLES = ["materials", "suppliers", "engineering_changes", "planning_groups",
                "bom", "inventory", "demand", "purchase_orders"]


def to_records(x) -> list[dict]:
    """DataFrame or iterable of dicts -> list of plain dicts, with NaN turned into None."""
    if x is None:
        return []
    if isinstance(x, pd.DataFrame):
        rows = x.to_dict("records")      # already native Python scalars; only missing markers need fixing
        for r in rows:
            for k, v in r.items():
                if v is pd.NA or v is pd.NaT or (isinstance(v, float) and v != v):
                    r[k] = None
        return rows
    return [dict(r) for r in x]


def as_int(v) -> int | None:
    """Integral number (int, 6.0, '6') -> int; anything else (None, bool, 6.5, 'W6') -> None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else None


def as_num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f   # NaN check


def load_csv_data(directory: str | Path = SYNTHETIC_DIR) -> dict[str, pd.DataFrame]:
    directory = Path(directory)
    return {t: pd.read_csv(directory / f"{t}.csv") for t in INPUT_TABLES}


def load_data_to_db(conn: sqlite3.Connection, data: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace the input tables with `data` atomically: either every row loads or none do."""
    counts = {}
    with conn:
        for t in reversed(INPUT_TABLES):
            conn.execute(f"DELETE FROM {t}")
        for t in INPUT_TABLES:
            rows = to_records(data[t])
            if rows:
                cols = list(rows[0])
                conn.executemany(
                    f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                    [tuple(r[c] for c in cols) for r in rows])
            counts[t] = len(rows)
    return counts


def load_data_from_db(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    return {t: pd.read_sql_query(f"SELECT * FROM {t}", conn) for t in INPUT_TABLES}


def save_simulation_run(conn: sqlite3.Connection, result: dict) -> str:
    """Store a simulate_inventory() result and its exceptions. Re-saving identical inputs is a no-op."""
    if not result.get("simulation_id"):
        raise ValueError("result has no simulation_id")
    if conn.execute("SELECT 1 FROM engineering_changes WHERE change_id = ?", (result.get("change_id"),)).fetchone() is None:
        raise ValueError(f"engineering change {result.get('change_id')!r} is not in the database; insert it before saving runs")
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO simulation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (result["simulation_id"], result["change_id"], result["scenario_id"], result["input_snapshot_hash"],
             result["engine_version"], datetime.now(timezone.utc).isoformat(timespec="seconds"),
             result["validation_status"], result["total_shortage_units"], result["excess_value"],
             (result.get("excess") or {}).get("rev_b_scrap_units"),
             (result.get("excess") or {}).get("rev_c_closing_units"),
             json.dumps(result, sort_keys=True)))
        conn.executemany(
            "INSERT OR IGNORE INTO exceptions (simulation_id, exception_id, change_id, exception_type, material_id, week,"
            " quantity, financial_impact, severity_score, severity_level, severity_rank, description,"
            " recommended_action, owner_role, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(result["simulation_id"], e["exception_id"], result["change_id"], e["exception_type"], e["material_id"],
              e["week"], e["quantity"], e["financial_impact"], e["severity_score"], e["severity_level"],
              e["severity_rank"], e["description"], e["recommended_action"], e["owner_role"], e["status"])
             for e in result.get("exceptions", [])])
    return result["simulation_id"]
