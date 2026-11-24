import json

import pandas as pd

from engine.bom_impact import (find_bom_cycles, generate_bom_impact_report, get_affected_assemblies,
                               get_parent_materials, trace_where_used)


def test_direct_parents(data):
    assert get_parent_materials("MAT-101", data["bom"]) == ["KIT-301", "SUB-201"]


def test_multi_level_paths_with_multiple_parents(data):
    paths = sorted(p["ids"] for p in trace_where_used("MAT-101", data["bom"])["paths"])
    assert paths == [["KIT-301", "MAT-101"], ["PUMP-001", "SUB-201", "MAT-101"], ["PUMP-002", "SUB-201", "MAT-101"]]


def test_affected_assemblies(data):
    a = get_affected_assemblies("MAT-101", data["bom"])
    assert a["direct_parents"] == ["KIT-301", "SUB-201"]
    assert a["indirect_parents"] == ["PUMP-001", "PUMP-002"]
    assert a["top_level_products"] == ["KIT-301", "PUMP-001", "PUMP-002"]


def test_report_matches_spec_shape(data, change):
    r = generate_bom_impact_report("MAT-101", data["bom"], data["materials"], change)
    assert r["material"] == "MAT-101" and r["old_revision"] == "Rev B" and r["impact_status"] == "IDENTIFIED"
    pump = next(a for a in r["affected_assemblies"] if a["assembly"] == "PUMP-001")
    assert pump["path"] == ["Pump Assembly", "Mounting Sub-Assembly", "Mounting Bracket Rev B"]
    json.dumps(r)                                       # exportable


def test_cycle_detected_and_traversal_terminates(data):
    bom = pd.concat([data["bom"], pd.DataFrame([{"bom_id": "BOM-X", "parent_material_id": "MAT-101",
                                                 "child_material_id": "PUMP-001", "quantity_per_parent": 1,
                                                 "effective_from": 1}])], ignore_index=True)
    assert find_bom_cycles(bom)
    r = generate_bom_impact_report("MAT-101", bom, data["materials"])
    assert r["impact_status"] == "CYCLE_DETECTED" and r["cycles"]


def test_missing_material(data):
    assert generate_bom_impact_report("MAT-999", data["bom"], data["materials"])["impact_status"] == "MATERIAL_NOT_FOUND"


def test_unused_material(data):
    assert generate_bom_impact_report("PUMP-001", data["bom"], data["materials"])["impact_status"] == "NO_WHERE_USED"


def test_quantity_multiplies_along_path(data):
    r = generate_bom_impact_report("MAT-203", data["bom"], data["materials"])
    assert {a["assembly"]: a["quantity_per_assembly"] for a in r["affected_assemblies"]} == {"PUMP-001": 4, "PUMP-002": 4}
