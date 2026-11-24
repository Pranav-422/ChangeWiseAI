import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.data_loader import load_csv_data, to_records  # noqa: E402
from engine.inventory import simulate_inventory  # noqa: E402


@pytest.fixture
def data():
    return load_csv_data()


@pytest.fixture
def change(data):
    return to_records(data["engineering_changes"])[0]


@pytest.fixture
def run(data, change):
    """run(**overrides): simulate the base data with table / change / parameter overrides."""
    def _run(change_updates=None, purchase_orders=None, inventory=None, demand=None, suppliers=None, **params):
        return simulate_inventory(
            data["materials"],
            data["inventory"] if inventory is None else inventory,
            data["demand"] if demand is None else demand,
            data["purchase_orders"] if purchase_orders is None else purchase_orders,
            {**change, **(change_updates or {})},
            data["suppliers"] if suppliers is None else suppliers,
            **params)
    return _run


def edit(df: pd.DataFrame, mask_col, mask_val, **values) -> pd.DataFrame:
    out = df.copy()
    for col, val in values.items():
        out.loc[out[mask_col] == mask_val, col] = val
    return out


def week(result, n):
    return result["weeks"][n - 1]
