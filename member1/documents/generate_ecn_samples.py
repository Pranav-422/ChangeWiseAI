"""Create the 18-document ECN test collection for Member 3's extractor, then verify it with PyMuPDF.

Outputs:
  documents/ecn_samples/ECN-0NN.pdf       the documents
  documents/expected_outputs/ECN-0NN.json the ground truth an extractor must return
  documents/manifest.json                 category + per-field status for every document

Field status vocabulary (used to score field-level extraction accuracy):
  PRESENT    value is stated once and clearly -> expected value is that value
  MISSING    not in the document              -> expected value is null (never defaulted)
  AMBIGUOUS  stated but unclear               -> expected value is null, source text preserved
  INVALID    stated clearly but impossible    -> expected value is the stated value (extract, then flag)
  CONFLICT   stated twice with different values -> expected value is null, both values preserved

Run:  python documents/generate_ecn_samples.py
"""
import json
from pathlib import Path

import pymupdf

DOC_DIR = Path(__file__).resolve().parent
PDF_DIR, JSON_DIR = DOC_DIR / "ecn_samples", DOC_DIR / "expected_outputs"
FIELDS = ["change_id", "part_number", "old_revision", "new_revision", "effective_week", "use_up_end_week",
          "interchangeability", "reason", "approver", "approval_status"]
LABELS = {"change_id": "ECN No", "part_number": "Part Number", "old_revision": "Current Revision",
          "new_revision": "New Revision", "effective_week": "Effective Week", "use_up_end_week": "Old Revision Use-Up End",
          "interchangeability": "Interchangeable", "reason": "Reason for Change", "approver": "Approved By",
          "approval_status": "Approval Status"}


def _base(cid, part, desc, old, new, eff, use, inter, reason, approver, status="Approved"):
    return {"change_id": cid, "part_number": part, "description": desc, "old_revision": old, "new_revision": new,
            "effective_week": eff, "use_up_end_week": use, "interchangeability": inter, "reason": reason,
            "approver": approver, "approval_status": status}


def _render(field, value):
    if field in ("effective_week", "use_up_end_week"):
        return f"W{value}"
    if field == "interchangeability":
        return "Yes - fully interchangeable" if value else "No - not interchangeable"
    return str(value)


# Each sample: category, base values, and per-field overrides:
#   omit=[fields]                      line removed                     -> MISSING
#   text={field: "free text"}          line replaced by unclear text    -> AMBIGUOUS
#   invalid={field: reason}            value kept, flagged              -> INVALID
#   conflict={field: (other, extra_line)} second contradicting line     -> CONFLICT
SAMPLES = [
    ("complete", _base("ECN-001", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                       "Improved mechanical durability", "Engineering Manager"), {}),
    ("complete", _base("ECN-002", "MAT-202", "Impeller", "Rev A", "Rev B", 8, 7, False,
                       "Cavitation erosion at blade tips; revised blade profile", "Chief Design Engineer"), {}),
    ("complete", _base("ECN-003", "MAT-203", "Hex Bolt M10", "Rev A", "Rev B", 4, 3, True,
                       "Zinc-flake coating for corrosion resistance", "Quality Manager"), {}),
    ("complete", _base("ECN-004", "MAT-201", "Motor 5kW", "Rev A", "Rev B", 10, 9, False,
                       "Higher-efficiency IE3 winding", "Engineering Manager"), {}),
    ("complete", _base("ECN-005", "SUB-201", "Mounting Sub-Assembly", "Rev A", "Rev B", 7, 6, True,
                       "Weld sequence change to reduce distortion", "Manufacturing Engineering Lead", "Pending"), {}),
    ("missing_fields", _base("ECN-006", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                             "Improved mechanical durability", "Engineering Manager"), {"omit": ["effective_week"]}),
    ("missing_fields", _base("ECN-007", "MAT-202", "Impeller", "Rev A", "Rev B", 9, 8, False,
                             "Revised hub keyway tolerance", "Chief Design Engineer"), {"omit": ["approver"]}),
    ("missing_fields", _base("ECN-008", "MAT-203", "Hex Bolt M10", "Rev A", "Rev B", 5, 4, True,
                             "Change of thread class to 6g", "Quality Manager"),
     {"omit": ["use_up_end_week", "interchangeability"]}),
    ("missing_fields", _base("ECN-009", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                             "Improved mechanical durability", "Engineering Manager"), {"omit": ["part_number"]}),
    ("ambiguous_fields", _base("ECN-010", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                               "Improved mechanical durability", "Engineering Manager"),
     {"text": {"effective_week": "around week 6 or 7, subject to supplier confirmation"}}),
    ("ambiguous_fields", _base("ECN-011", "MAT-202", "Impeller", "Rev A", "Rev B", 8, 7, True,
                               "Cavitation erosion at blade tips", "Chief Design Engineer"),
     {"text": {"interchangeability": "interchangeable where practical - check with assembly"}}),
    ("ambiguous_fields", _base("ECN-012", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                               "Improved mechanical durability", "Engineering Manager"),
     {"text": {"part_number": "MAT-101 (or MAT-110 per superseded drawing)"}}),
    ("ambiguous_fields", _base("ECN-013", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                               "Improved mechanical durability", "Engineering Manager"),
     {"text": {"use_up_end_week": "until existing stock is exhausted"}}),
    ("incorrect_dates", _base("ECN-014", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 9, False,
                              "Improved mechanical durability", "Engineering Manager"),
     {"invalid": {"use_up_end_week": "Use-up end W9 is after effective week W6 but revisions are not interchangeable"}}),
    ("incorrect_dates", _base("ECN-015", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 0, 5, True,
                              "Improved mechanical durability", "Engineering Manager"),
     {"invalid": {"effective_week": "Week 0 does not exist; weeks start at W1"}}),
    ("incorrect_dates", _base("ECN-016", "MAT-202", "Impeller", "Rev A", "Rev B", 58, 57, False,
                              "Revised blade profile", "Chief Design Engineer"),
     {"invalid": {"effective_week": "W58 is beyond a 52-week calendar",
                  "use_up_end_week": "W57 is beyond a 52-week calendar"}}),
    ("conflicting_revisions", _base("ECN-017", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                                    "Improved mechanical durability", "Engineering Manager"),
     {"conflict": {"old_revision": ("Rev A", "Note: this change supersedes Rev A of MAT-101.")}}),
    ("conflicting_revisions", _base("ECN-018", "MAT-101", "Mounting Bracket", "Rev B", "Rev C", 6, 5, True,
                                    "Improved mechanical durability", "Engineering Manager"),
     {"conflict": {"new_revision": ("Rev D", "Released drawing reference: MAT-101 Rev D, sheet 1 of 2.")}}),
]


def build_sample(category, values, mods):
    omit, text = mods.get("omit", []), mods.get("text", {})
    invalid, conflict = mods.get("invalid", {}), mods.get("conflict", {})
    lines = ["ENGINEERING CHANGE NOTICE", "Pump Plant PUMP-PLANT-01  |  Synthetic test document", ""]
    for f in FIELDS:
        if f in omit:
            continue
        lines.append(f"{LABELS[f]}: {text.get(f, _render(f, values[f]))}")
        if f == "part_number":
            lines.append(f"Description: {values['description']}")
    lines += ["", "Notes:"] + [extra for _, extra in conflict.values()] + ["Released for planning review."]

    expected, status = {}, {}
    for f in FIELDS:
        status[f] = ("MISSING" if f in omit else "AMBIGUOUS" if f in text else
                     "CONFLICT" if f in conflict else "INVALID" if f in invalid else "PRESENT")
        expected[f] = values[f] if status[f] in ("PRESENT", "INVALID") else None
    truth = {
        "document": f"{values['change_id']}.pdf",
        "category": category,
        "expected": expected,
        "field_status": status,
        "missing_fields": [f for f in FIELDS if status[f] == "MISSING"],
        "ambiguous_fields": [{"field": f, "source_text": t} for f, t in text.items()],
        "conflicts": [{"field": f, "values": [values[f], other]} for f, (other, _) in conflict.items()],
        "invalid_fields": [{"field": f, "value": values[f], "reason": r} for f, r in invalid.items()],
        "requires_human_review": any(s != "PRESENT" for s in status.values()) or values["approval_status"] != "Approved",
    }
    if status["change_id"] != "PRESENT":
        raise ValueError("change_id must stay present: it names the file")
    return lines, truth


def write_collection():
    PDF_DIR.mkdir(exist_ok=True)
    JSON_DIR.mkdir(exist_ok=True)
    manifest = []
    for category, values, mods in SAMPLES:
        lines, truth = build_sample(category, values, mods)
        cid = values["change_id"]
        doc = pymupdf.open()
        page = doc.new_page()
        y = 72
        for i, line in enumerate(lines):
            page.insert_text((72, y), line, fontsize=14 if i == 0 else 11, fontname="helv")
            y += 22 if i == 0 else 17
        # Fixed dates + no new file ID: regenerating gives byte-identical PDFs (no Git churn).
        doc.set_metadata({"title": f"{cid} (synthetic)", "author": "ChangeWise AI test collection",
                          "creationDate": "D:20261123000000", "modDate": "D:20261123000000"})
        doc.save(PDF_DIR / f"{cid}.pdf", deflate=True, no_new_id=True)
        doc.close()
        (JSON_DIR / f"{cid}.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
        manifest.append({"document": truth["document"], "expected_output": f"expected_outputs/{cid}.json",
                         "category": category, "field_status": truth["field_status"],
                         "requires_human_review": truth["requires_human_review"]})
    counts = {c: sum(m["category"] == c for m in manifest) for c in dict.fromkeys(m["category"] for m in manifest)}
    (DOC_DIR / "manifest.json").write_text(json.dumps(
        {"total_documents": len(manifest), "fields_per_document": len(FIELDS),
         "category_counts": counts, "documents": manifest}, indent=2), encoding="utf-8")
    return manifest


def verify_collection() -> list[str]:
    """Re-open every PDF with PyMuPDF and check each stated value is present in the extracted text."""
    problems = []
    for path in sorted(JSON_DIR.glob("ECN-*.json")):
        truth = json.loads(path.read_text(encoding="utf-8"))
        with pymupdf.open(PDF_DIR / truth["document"]) as doc:
            text = "".join(page.get_text() for page in doc)
        for f, v in truth["expected"].items():
            if v is not None and _render(f, v) not in text:
                problems.append(f"{truth['document']}: '{_render(f, v)}' ({f}) not extractable")
        for a in truth["ambiguous_fields"]:
            if a["source_text"] not in text:
                problems.append(f"{truth['document']}: ambiguous text for {a['field']} not extractable")
        for c in truth["conflicts"]:
            if not all(str(v) in text for v in c["values"]):
                problems.append(f"{truth['document']}: conflicting values for {c['field']} not extractable")
    return problems


if __name__ == "__main__":
    m = write_collection()
    issues = verify_collection()
    print(f"Wrote {len(m)} ECN PDFs + expected JSON. PyMuPDF verification: {'OK' if not issues else issues}")
