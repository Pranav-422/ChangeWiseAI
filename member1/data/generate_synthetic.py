"""Write the eight SAP-like base-scenario CSVs to data/synthetic/.

The base scenario is fully specified (no random draws), so the output is identical on every run.
Run:  python data/generate_synthetic.py
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "synthetic"
PLANT = "PUMP-PLANT-01"

MATERIALS = [
    # material_id, material_name, description, revision, material_type, material_status, unit_cost, uom
    ("PUMP-001", "Pump Assembly", "Centrifugal pump PA-500, finished good", "Rev A", "FINISHED", "Active", 12000, "EA"),
    ("PUMP-002", "Compact Pump Assembly", "Centrifugal pump PA-300, finished good", "Rev A", "FINISHED", "Active", 9500, "EA"),
    ("KIT-301", "Bracket Service Kit", "Field replacement kit (spares)", "Rev A", "KIT", "Active", 900, "EA"),
    ("SUB-201", "Mounting Sub-Assembly", "Motor mounting sub-assembly", "Rev A", "ASSEMBLY", "Active", 1500, "EA"),
    ("MAT-101", "Mounting Bracket Rev B", "Welded steel mounting bracket", "Rev B", "COMPONENT", "Phase-Out", 400, "EA"),
    ("MAT-102", "Mounting Bracket Rev C", "Redesigned bracket, improved durability", "Rev C", "COMPONENT", "Released", 450, "EA"),
    ("MAT-201", "Motor 5kW", "Induction motor 5 kW", "Rev A", "COMPONENT", "Active", 6000, "EA"),
    ("MAT-202", "Impeller", "Cast impeller 180 mm", "Rev A", "COMPONENT", "Active", 1200, "EA"),
    ("MAT-203", "Hex Bolt M10", "Hex bolt M10 x 40, zinc plated", "Rev A", "COMPONENT", "Active", 5, "EA"),
]

BOM = [
    # bom_id, parent, child, qty_per_parent, effective_from (week), effective_to (week, blank = open)
    ("BOM-001", "PUMP-001", "SUB-201", 1, 1, None),
    ("BOM-002", "PUMP-002", "SUB-201", 1, 1, None),
    ("BOM-003", "SUB-201", "MAT-101", 1, 1, 5),
    ("BOM-004", "SUB-201", "MAT-102", 1, 6, None),
    ("BOM-005", "KIT-301", "MAT-101", 1, 1, 5),
    ("BOM-006", "PUMP-001", "MAT-201", 1, 1, None),
    ("BOM-007", "PUMP-001", "MAT-202", 1, 1, None),
    ("BOM-008", "PUMP-002", "MAT-202", 1, 1, None),
    ("BOM-009", "SUB-201", "MAT-203", 4, 1, None),
]

INVENTORY = [
    # inventory_id, material_id, on_hand, reserved, safety_stock
    ("INV-001", "MAT-101", 500, 50, 30),   # 50 reserved for KIT-301 service orders
    ("INV-002", "MAT-102", 0, 0, 20),
    ("INV-003", "MAT-201", 40, 0, 10),
    ("INV-004", "MAT-202", 150, 10, 20),
    ("INV-005", "MAT-203", 5000, 0, 500),
]

WEEKLY_BRACKETS = [80, 100, 100, 120, 120, 150, 150, 150]   # agreed base demand, W1..W8

SUPPLIERS = [
    # id, name, status, lead_time_weeks, expedite_available, expedited_lead_time_weeks, expedite_fee, restriction_note
    ("S1", "Alpha Precision Castings", "Approved", 3, 0, None, 0, None),
    ("S2", "Bravo Forgings", "Approved", 4, 1, 3, 12000, None),
    ("S3", "Charlie Metal Works", "Blocked", 3, 0, None, 0, "Blocked: open quality notification QN-4471 (weld porosity)"),
    ("S4", "Delta Fabrication", "Unqualified", 2, 1, 1, 8000, "Unqualified: PPAP for Rev C bracket not approved"),
    ("S5", "Echo Pump Components", "Approved", 2, 0, None, 0, None),
]

PLANNING_GROUPS = [
    # group_id, group_name, material_id, supplier_id, authorization_status
    ("PG-10", "Bracket Purchasing", "MAT-101", "S1", "Authorized"),
    ("PG-10", "Bracket Purchasing", "MAT-102", "S2", "Authorized"),
    ("PG-10", "Bracket Purchasing", "MAT-102", "S3", "Unauthorized"),
    ("PG-20", "Alternate Source Purchasing", "MAT-102", "S4", "Unauthorized"),
    ("PG-30", "General Components", "MAT-202", "S5", "Authorized"),
    ("PG-30", "General Components", "MAT-203", "S3", "Authorized"),
]

PURCHASE_ORDERS = [
    # po_id, material, supplier, qty, order_week, arrival_week, group, status, cancel_allowed_until,
    # maximum_defer_weeks, max_reduction_quantity, cancellation_fee, reduction_fee, expedite_fee, expedited
    ("PO-001", "MAT-101", "S1", 200, -2, 3, "PG-10", "Open", 1, 2, 200, 8000, 5000, 0, 0),
    ("PO-002", "MAT-101", "S1", 100, 0, 5, "PG-10", "Open", 3, 1, 100, 4000, 2000, 0, 0),
    ("PO-003", "MAT-102", "S2", 500, 2, 6, "PG-10", "Open", 3, 2, 200, 10000, 6000, 12000, 0),
    ("PO-004", "MAT-202", "S5", 120, -1, 2, "PG-30", "Open", 1, 1, 60, 3000, 1000, 0, 0),
    ("PO-005", "MAT-203", "S3", 2000, -1, 4, "PG-30", "Open", 2, 1, 2000, 500, 200, 0, 0),
]

ENGINEERING_CHANGES = [
    {
        "change_id": "ECN-001", "part_number": "MAT-101", "new_material_id": "MAT-102",
        "old_revision": "Rev B", "new_revision": "Rev C", "effective_week": 6, "use_up_end_week": 5,
        "interchangeability": 1, "reason": "Improved mechanical durability", "approver": "Engineering Manager",
        "approval_status": "Approved", "approval_week": 1, "created_at": "2026-11-20T09:00:00",
    }
]


def build_tables() -> dict[str, pd.DataFrame]:
    return {
        "materials": pd.DataFrame(MATERIALS, columns=[
            "material_id", "material_name", "description", "revision", "material_type",
            "material_status", "unit_cost", "unit_of_measure"]),
        "bom": pd.DataFrame(BOM, columns=[
            "bom_id", "parent_material_id", "child_material_id", "quantity_per_parent",
            "effective_from", "effective_to"]).astype({"effective_to": "Int64"}),
        "inventory": pd.DataFrame(
            [(i, m, PLANT, oh, r, s, "2026-11-23") for i, m, oh, r, s in INVENTORY],
            columns=["inventory_id", "material_id", "plant_id", "on_hand", "reserved", "safety_stock", "inventory_date"]),
        "demand": pd.DataFrame(
            [(f"D-{w:03d}", "PUMP-001", "MAT-101" if w <= 5 else "MAT-102", PLANT, w, q)
             for w, q in enumerate(WEEKLY_BRACKETS, start=1)],
            columns=["demand_id", "product_id", "material_id", "plant_id", "week", "required_quantity"]),
        "purchase_orders": pd.DataFrame(PURCHASE_ORDERS, columns=[
            "po_id", "material_id", "supplier_id", "quantity", "order_week", "arrival_week", "purchasing_group",
            "po_status", "cancel_allowed_until", "maximum_defer_weeks", "max_reduction_quantity",
            "cancellation_fee", "reduction_fee", "expedite_fee", "expedited"]),
        "suppliers": pd.DataFrame(SUPPLIERS, columns=[
            "supplier_id", "supplier_name", "supplier_status", "lead_time_weeks", "expedite_available",
            "expedited_lead_time_weeks", "expedite_fee", "restriction_note"]).astype({"expedited_lead_time_weeks": "Int64"}),
        "planning_groups": pd.DataFrame(PLANNING_GROUPS, columns=[
            "group_id", "group_name", "material_id", "supplier_id", "authorization_status"]),
        "engineering_changes": pd.DataFrame(ENGINEERING_CHANGES),
    }


def write_csvs(out_dir: Path = OUT) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, df in build_tables().items():
        df.to_csv(out_dir / f"{name}.csv", index=False, lineterminator="\n")   # LF on every OS: byte-stable CSVs
        counts[name] = len(df)
    return counts


if __name__ == "__main__":
    for name, n in write_csvs().items():
        print(f"{name:22s} {n:3d} rows")
