"""Member 1 on PostgreSQL data: the contract of member3/services/member1_adapter.py, tables from core.*.

Only the source of the eight input tables changes. Validation, BOM, simulation and severity are Member 1's.

A dataset key is the scenario name for Member 1's own change (as in the SQLite application) and
"base@<change>" for any other change: the scenario variants edit records of Member 1's change only.
"""
import io
import json

import pandas as pd

from member1.engine.data_loader import INPUT_TABLES
from member1.engine.scenarios import SCENARIOS, load_scenario
from member2.integration.member1_bridge import (  # noqa: F401  (simulate_inventory is part of the contract)
    CHANGE_ID, convert, simulate_inventory,
)
from member3.integration import member1_module as base
from member3.integration.member1_module import SYNTHETIC, sample_documents, score_exceptions  # noqa: F401

from ..core.database import read

# Order by primary key: file order and key order are the same in Member 1's CSVs.
_KEYS = {"materials": "material_id", "suppliers": "supplier_id", "engineering_changes": "change_id",
         "planning_groups": "group_id, material_id, supplier_id", "bom": "bom_id", "inventory": "inventory_id",
         "demand": "demand_id", "purchase_orders": "po_id"}


def load_tables():
    """The same DataFrames load_csv_data() gives. Passing through CSV text makes the column types identical."""
    columns = ", ".join(f"(SELECT coalesce(json_agg(t ORDER BY {_KEYS[n]}), '[]') FROM core.{n} t) AS {n}"
                        for n in INPUT_TABLES)
    with read() as db:  # one statement: one round trip, one consistent snapshot
        row = db.execute(f"SELECT {columns}").fetchone()
    tables = {}
    for name in INPUT_TABLES:
        records = json.loads(row[name])
        if not records:
            raise ValueError(f"core.{name} is empty; run scripts/migration/import_postgres.py")
        frame = pd.DataFrame(records)
        for column in frame:
            if frame[column].map(lambda v: isinstance(v, bool)).any():
                frame[column] = frame[column].astype(int)  # Member 1 stores flags as 0/1
        tables[name] = pd.read_csv(io.StringIO(frame.to_csv(index=False)))
    return tables


def key_of(change_id, scenario):
    return scenario if change_id == CHANGE_ID else f"{scenario}@{change_id}"


def change_of(key):
    return key.partition("@")[2] or CHANGE_ID


def list_scenarios():
    with read() as db:
        others = [r["change_id"] for r in db.execute(
            "SELECT change_id FROM core.engineering_changes WHERE change_id <> ? ORDER BY 1", [CHANGE_ID])]
    return [*SCENARIOS, *(f"base@{c}" for c in others)]


def scenario_tables(key):
    return load_scenario(key.partition("@")[0], load_tables())


def load_dataset(key):
    return convert(scenario_tables(key), key, change_of(key))


def validate_ecn(fields, dataset):
    return base.validate_ecn(fields, dataset, load_tables())


def bom_impact(material_id):
    return base.bom_impact(material_id, load_tables())
