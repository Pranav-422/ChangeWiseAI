"""Seeded test-scenario variants (deck slide 8). Each is the base dataset with one deliberate change.

Members 2 and 3 can use these to test hard rules and escalation. All variants are deterministic copies;
the base data is never modified.
"""
import pandas as pd

from .data_loader import load_csv_data

SCENARIOS = {
    "base": "Base scenario: Rev B -> Rev C, effective W6, use-up end W5.",
    "rev_c_supplier_delay": "Rev C PO-003 arrives two weeks late (W8).",
    "excess_rev_b_orders": "Rev B PO-002 increased from 100 to 400 units.",
    "blocked_supplier": "Rev C supplier S2 becomes Blocked (quality hold).",
    "date_conflict": "Rev B use-up end moved to W3 while Rev C stays effective W6 (W4-W5 gap).",
    "missing_records": "Rev C inventory record and S2 lead time are missing.",
}


def load_scenario(name: str, data: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario {name!r}; choose from {sorted(SCENARIOS)}")
    d = {k: v.copy() for k, v in (data or load_csv_data()).items()}
    po, sup, ecn, inv = d["purchase_orders"], d["suppliers"], d["engineering_changes"], d["inventory"]
    if name == "rev_c_supplier_delay":
        po.loc[po.po_id == "PO-003", "arrival_week"] = 8
    elif name == "excess_rev_b_orders":
        po.loc[po.po_id == "PO-002", "quantity"] = 400
    elif name == "blocked_supplier":
        sup.loc[sup.supplier_id == "S2", ["supplier_status", "restriction_note"]] = ["Blocked", "Blocked: quality hold QN-5102"]
    elif name == "date_conflict":
        ecn.loc[ecn.change_id == "ECN-001", "use_up_end_week"] = 3
    elif name == "missing_records":
        d["inventory"] = inv[inv.material_id != "MAT-102"].reset_index(drop=True)
        sup["lead_time_weeks"] = sup["lead_time_weeks"].astype("Float64")
        sup.loc[sup.supplier_id == "S2", "lead_time_weeks"] = None
    return d
