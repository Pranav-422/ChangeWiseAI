"""Member 1 behind the interface of services/member1_adapter.py. Translation only, no calculation."""
from member1.engine import ROOT as MEMBER1_ROOT
from member1.engine.bom_impact import generate_bom_impact_report
from member1.engine.data_loader import load_csv_data, to_records
from member1.engine.validation import validate_engineering_change
from member2.integration.member1_bridge import (  # noqa: F401  (part of the interface)
    list_scenarios, load_dataset, simulate_inventory,
)

from ..ai.ecn_extractor import extract_pdf_text

SYNTHETIC = True


def sample_documents():
    """Member 1's ECN test PDFs as {"id", "title", "text"}."""
    return [{"id": path.stem, "title": path.name, "text": extract_pdf_text(path.read_bytes())}
            for path in sorted((MEMBER1_ROOT / "documents" / "ecn_samples").glob("*.pdf"))]


def load_tables():
    return load_csv_data()


def validate_ecn(fields, dataset, tables=None):
    """Member 1's own ECN validation, plus the new material the document does not name."""
    tables = tables or load_tables()
    old = dataset["engineering_change"]["old_material_id"]
    new = dataset["engineering_change"]["new_material_id"]
    change = {"change_id": fields["change_id"], "part_number": fields["part_number"],
              "new_material_id": new if fields["part_number"] == old else None,
              "old_revision": f"Rev {fields['old_revision']}", "new_revision": f"Rev {fields['new_revision']}",
              "effective_week": fields["effective_week"], "use_up_end_week": fields["use_up_end_week"],
              "interchangeability": fields["interchangeability"],
              "approval_status": fields["approval_status"].title()}
    found = validate_engineering_change(change, tables["materials"]).to_dict()["issues"]
    return [{"code": i["code"], "field": i["record"].rpartition(".")[2], "message": i["description"]}
            for i in found if i["status"] != "VALID"]


def bom_impact(material_id, tables=None):
    tables = tables or load_tables()
    report = generate_bom_impact_report(material_id, tables["bom"], tables["materials"])
    return {"material_id": material_id, "direct_parents": report["direct_parents"],
            "indirect_parents": report["indirect_parents"],
            "finished_assemblies": report["affected_finished_products"],
            "paths": sorted(a["path_ids"][::-1] for a in report["affected_assemblies"]),
            "impact_status": report["impact_status"],
            "names": {m["material_id"]: m["material_name"] for m in to_records(tables["materials"])}}


def score_exceptions(dataset, simulation):
    """Member 1 scores and ranks inside its simulation result."""
    return [{"exception_id": f"EXC-{e['severity_rank']:03d}", "source_id": e["exception_id"],
             "type": e["exception_type"], "week": e["week"], "units": e["quantity"] or 0,
             "impact_rs": e["financial_impact"], "severity": e["severity_score"],
             "band": e["severity_level"].capitalize(), "description": e["description"],
             "owner_role": e["owner_role"], "recommended_action": e["recommended_action"]}
            for e in simulation["exceptions"]]
