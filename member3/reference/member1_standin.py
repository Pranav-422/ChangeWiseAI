"""TEMPORARY STAND-IN for Member 1's module, until it is merged.

Member 1 owns the data, master-data validation, BOM traversal, inventory simulation and severity
scoring. Application code reaches this only through services/member1_adapter.py; replace it with
`member1.module` in config/settings.yaml.
"""
from member2.reference.scenarios import SCENARIOS
from member2.reference.simulator import simulate_inventory  # noqa: F401  (part of Member 1's interface)

SYNTHETIC = True
PART_NUMBER = "BRK-100"
# (parent, child): the full assembly structure around the changed bracket.
BOM_EDGES = [("PUMP-ASSY", "MOUNT-SUB"), ("MOUNT-SUB", "BRK-B"), ("SPARE-KIT", "BRK-B")]
SEVERITY_BANDS = [("Critical", 40000), ("High", 10000), ("Medium", 2000), ("Low", 0)]


def list_scenarios():
    return list(SCENARIOS)


def load_dataset(scenario_id):
    data = SCENARIOS[scenario_id]()
    for material in data["materials"]:
        material["part_number"] = PART_NUMBER
    return data


def validate_ecn(fields, dataset):
    """Check an extracted ECN against material and engineering-change records."""
    errors = []

    def bad(code, field, message):
        errors.append({"code": code, "field": field, "message": message})

    revisions = {m["revision"]: m["material_id"] for m in dataset["materials"]
                 if m["part_number"] == fields["part_number"]}
    if not revisions:
        bad("UNKNOWN_PART", "part_number", f"{fields['part_number']} is not in the item master.")
    else:
        for field in ("old_revision", "new_revision"):
            if fields[field] not in revisions:
                bad("UNKNOWN_REVISION", field, f"{fields['part_number']} has no revision {fields[field]}.")
    record = dataset["engineering_change"]
    if fields["change_id"] != record["change_id"]:
        bad("UNKNOWN_CHANGE", "change_id", f"{fields['change_id']} has no engineering-change record.")
        return errors
    known = {v: k for k, v in revisions.items()}
    expected = {"old_revision": known.get(record["old_material_id"]), "new_revision": known.get(record["new_material_id"]),
                "effective_week": record["effective_week"], "use_up_end_week": record["use_up_end_week"],
                "interchangeability": bool(record["interchangeable"]), "approval_status": record["status"]}
    for field, value in expected.items():
        if revisions and fields[field] != value:
            bad("RECORD_MISMATCH", field, f"Document says {fields[field]}, record {record['change_id']} says {value}.")
    return errors


def bom_impact(material_id):
    """Reverse where-used with every path from the changed material to a finished assembly."""
    paths = []

    def climb(item, path):
        parents = [p for p, child in BOM_EDGES if child == item]
        if not parents:
            paths.append(path)
        for parent in parents:
            climb(parent, path + [parent])

    climb(material_id, [material_id])
    paths = [p for p in paths if len(p) > 1]
    direct = sorted({p[1] for p in paths})
    return {"material_id": material_id, "direct_parents": direct,
            "indirect_parents": sorted({n for p in paths for n in p[2:]} - set(direct)),
            "finished_assemblies": sorted({p[-1] for p in paths}), "paths": sorted(paths),
            "impact_status": "IMPACTED" if paths else "NOT_USED"}


def score_exceptions(dataset, simulation):
    """Severity = impact x 1 / (weeks to event + 1) x criticality (solution plan, idea 4)."""
    change, now = dataset["engineering_change"], dataset["planning_week"]
    cost = {m["material_id"]: m["unit_cost"] for m in dataset["materials"]}
    rev_b, rev_c = change["old_material_id"], change["new_material_id"]
    found = []

    def add(kind, week, units, unit_cost, criticality, text):
        impact = units * unit_cost
        severity = round(impact / (max(0, week - now) + 1) * criticality, 2)
        found.append({"type": kind, "week": week, "units": units, "impact_rs": impact, "criticality": criticality,
                      "severity": severity, "description": text,
                      "band": next(name for name, floor in SEVERITY_BANDS if severity >= floor)})

    for row in simulation["weekly"]:
        if row["shortage"]:
            add("SHORTAGE", row["week"], row["shortage"], cost[rev_c], 3,
                f"{row['shortage']} units of demand unmet in W{row['week']}")
    if simulation["rev_b_leftover"]:
        add("EXCESS_REV_B", change["use_up_end_week"], simulation["rev_b_leftover"], cost[rev_b], 1,
            f"{simulation['rev_b_leftover']} Rev B units left after use-up end")
    blocked = {s["supplier_id"] for s in dataset["suppliers"] if s["status"] != "APPROVED"}
    for po in dataset["purchase_orders"]:
        if po["status"] not in ("OPEN", "CONFIRMED"):
            continue
        if po["supplier_id"] in blocked:
            add("SOURCING_BLOCK", po["arrival_week"], po["quantity"], cost[po["material_id"]], 2,
                f"{po['po_id']} is with supplier {po['supplier_id']}, which is not approved")
        if po["material_id"] == rev_c and po["arrival_week"] > change["effective_week"] and any(
                w["shortage"] and w["week"] < po["arrival_week"] for w in simulation["weekly"]):
            add("PO_TIMING", po["arrival_week"], po["quantity"], cost[rev_c], 1,
                f"{po['po_id']} arrives in W{po['arrival_week']}, after a shortage starts")
    found.sort(key=lambda e: (-e["severity"], e["type"], e["week"]))
    return [{"exception_id": f"EXC-{i:03d}", **e} for i, e in enumerate(found, 1)]
