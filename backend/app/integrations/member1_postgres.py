"""Member 1 on PostgreSQL data: the contract of member3/services/member1_adapter.py, tables from core.*.

Only the source of the eight input tables changes. Validation, BOM, simulation and severity are Member 1's.
"""
import io

import pandas as pd

from member1.engine.data_loader import INPUT_TABLES, to_records
from member1.engine.scenarios import SCENARIOS, load_scenario
from member2.integration.member1_bridge import convert, simulate_inventory  # noqa: F401  (part of the contract)
from member3.integration import member1_module as base
from member3.integration.member1_module import SYNTHETIC, sample_documents, score_exceptions  # noqa: F401

from ..core.database import read

# Order by primary key: file order and key order are the same in Member 1's CSVs.
_KEYS = {"materials": "material_id", "suppliers": "supplier_id", "engineering_changes": "change_id",
         "planning_groups": "group_id, material_id, supplier_id", "bom": "bom_id", "inventory": "inventory_id",
         "demand": "demand_id", "purchase_orders": "po_id"}


def load_tables():
    """The same DataFrames load_csv_data() gives. Passing through CSV text makes the column types identical."""
    tables = {}
    with read() as db:
        for name in INPUT_TABLES:
            cursor = db.execute(f"SELECT * FROM core.{name} ORDER BY {_KEYS[name]}")
            columns = [c.name for c in cursor.description]
            frame = pd.DataFrame(cursor.fetchall(), columns=columns)
            for column in columns:
                if frame[column].map(lambda v: isinstance(v, bool)).any():
                    frame[column] = frame[column].astype(int)  # Member 1 stores flags as 0/1
            tables[name] = pd.read_csv(io.StringIO(frame.to_csv(index=False)))
    return tables


def list_scenarios():
    return list(SCENARIOS)


def list_changes():
    return to_records(load_tables()["engineering_changes"])


def scenario_tables(scenario_id):
    return load_scenario(scenario_id, load_tables())


def load_dataset(scenario_id):
    return convert(scenario_tables(scenario_id), scenario_id)


def validate_ecn(fields, dataset):
    return base.validate_ecn(fields, dataset, load_tables())


def bom_impact(material_id):
    return base.bom_impact(material_id, load_tables())
