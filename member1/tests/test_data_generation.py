import importlib.util
import json

from engine import ROOT
from engine.data_loader import INPUT_TABLES, load_csv_data, to_records


def _module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generator_is_reproducible(tmp_path):
    gen = _module(ROOT / "data" / "generate_synthetic.py")
    gen.write_csvs(tmp_path)
    for t in INPUT_TABLES:
        assert (tmp_path / f"{t}.csv").read_bytes() == (ROOT / "data" / "synthetic" / f"{t}.csv").read_bytes()


def test_referential_integrity_and_rules(data):
    mats = {m["material_id"] for m in to_records(data["materials"])}
    sups = {s["supplier_id"]: s for s in to_records(data["suppliers"])}
    assert data["materials"]["material_id"].is_unique and data["purchase_orders"]["po_id"].is_unique
    assert set(data["bom"]["parent_material_id"]) | set(data["bom"]["child_material_id"]) <= mats
    assert set(data["purchase_orders"]["supplier_id"]) <= set(sups)
    assert set(data["purchase_orders"]["purchasing_group"]) <= set(data["planning_groups"]["group_id"])
    assert {s["supplier_status"] for s in sups.values()} == {"Approved", "Blocked", "Unqualified"}
    for col in ("on_hand", "reserved", "safety_stock"):
        assert (data["inventory"][col] >= 0).all()
    assert (data["inventory"]["reserved"] <= data["inventory"]["on_hand"]).all()
    assert (data["purchase_orders"]["quantity"] >= 0).all() and (data["demand"]["required_quantity"] >= 0).all()
    assert set(data["inventory"]["material_id"]) <= mats and set(data["demand"]["material_id"]) <= mats


def test_base_scenario_values(data):
    inv = {r["material_id"]: r for r in to_records(data["inventory"])}
    assert (inv["MAT-101"]["on_hand"], inv["MAT-101"]["reserved"], inv["MAT-101"]["safety_stock"]) == (500, 50, 30)
    assert (inv["MAT-102"]["on_hand"], inv["MAT-102"]["safety_stock"]) == (0, 20)
    assert list(data["demand"].sort_values("week")["required_quantity"]) == [80, 100, 100, 120, 120, 150, 150, 150]
    po = data["purchase_orders"].set_index("po_id")
    assert po.loc[["PO-001", "PO-002"], "quantity"].sum() == 300
    assert tuple(po.loc["PO-003", ["material_id", "supplier_id"]]) == ("MAT-102", "S2")
    s2 = data["suppliers"].set_index("supplier_id").loc["S2"]
    assert s2["supplier_status"] == "Approved" and s2["lead_time_weeks"] == 4


def test_ecn_collection_distribution_and_ground_truth():
    manifest = json.loads((ROOT / "documents" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_documents"] == 18
    assert manifest["category_counts"] == {"complete": 5, "missing_fields": 4, "ambiguous_fields": 4,
                                           "incorrect_dates": 3, "conflicting_revisions": 2}
    for d in manifest["documents"]:
        truth = json.loads((ROOT / "documents" / d["expected_output"]).read_text(encoding="utf-8"))
        assert (ROOT / "documents" / "ecn_samples" / d["document"]).exists()
        for f, status in truth["field_status"].items():
            assert (truth["expected"][f] is None) == (status in ("MISSING", "AMBIGUOUS", "CONFLICT"))
        if d["category"] == "complete":
            assert set(truth["field_status"].values()) == {"PRESENT"}


def test_ecn_pdfs_are_extractable_with_pymupdf():
    gen = _module(ROOT / "documents" / "generate_ecn_samples.py")
    assert gen.verify_collection() == []


def test_ecn_pdfs_regenerate_byte_identical():
    pdfs = sorted((ROOT / "documents" / "ecn_samples").glob("ECN-*.pdf"))
    before = {p.name: p.read_bytes() for p in pdfs}
    _module(ROOT / "documents" / "generate_ecn_samples.py").write_collection()
    assert {p.name: p.read_bytes() for p in pdfs} == before
