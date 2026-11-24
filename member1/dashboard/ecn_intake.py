"""Standalone ECN test-collection viewer. Run:  streamlit run dashboard/ecn_intake.py

Shows each synthetic ECN, its PyMuPDF-extracted text, the ground-truth fields, and what Member 1's validator says
about those fields against the material master. LLM extraction itself is Member 3's job.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import pymupdf  # noqa: E402
import streamlit as st  # noqa: E402

from engine import ROOT  # noqa: E402
from engine.data_loader import load_csv_data, to_records  # noqa: E402
from engine.validation import validate_engineering_change  # noqa: E402

DOCS = ROOT / "documents"
st.set_page_config(page_title="ChangeWise - ECN intake", layout="wide")
st.title("ECN intake - test collection")
st.caption("Synthetic ECN documents for measuring field-level extraction accuracy.")

manifest = json.loads((DOCS / "manifest.json").read_text(encoding="utf-8"))
st.write(f"{manifest['total_documents']} documents × {manifest['fields_per_document']} fields · "
         + ", ".join(f"{k}: {v}" for k, v in manifest["category_counts"].items()))
names = [d["document"] for d in manifest["documents"]]
uploaded = st.file_uploader("…or upload your own ECN PDF to see its extracted text", type="pdf")
choice = st.selectbox("Sample document", names,
                      format_func=lambda n: f"{n} ({next(d['category'] for d in manifest['documents'] if d['document'] == n)})")

pdf_bytes = uploaded.read() if uploaded else (DOCS / "ecn_samples" / choice).read_bytes()
with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
    text = "".join(p.get_text() for p in doc)
left, right = st.columns(2)
left.subheader("Extracted text (PyMuPDF)")
left.code(text or "(no extractable text - ask for a better scan or manual entry)", language=None)
if uploaded:
    st.stop()

truth = json.loads((DOCS / "expected_outputs" / choice.replace(".pdf", ".json")).read_text(encoding="utf-8"))
right.subheader("Expected structured output")
right.dataframe(pd.DataFrame([{"field": f, "expected": "null" if v is None else str(v), "status": truth["field_status"][f]}
                              for f, v in truth["expected"].items()]), hide_index=True, use_container_width=True)
for a in truth["ambiguous_fields"]:
    right.warning(f"Ambiguous {a['field']}: “{a['source_text']}”")
for c in truth["conflicts"]:
    right.error(f"Conflicting {c['field']}: {c['values']}")
for i in truth["invalid_fields"]:
    right.error(f"Invalid {i['field']} = {i['value']}: {i['reason']}")

st.subheader("Member 1 validation against the material master")
data = load_csv_data()
known = {c["part_number"]: c["new_material_id"] for c in to_records(data["engineering_changes"])}
change = {**truth["expected"], "new_material_id": known.get(truth["expected"]["part_number"])}
result = validate_engineering_change(change, data["materials"])
st.markdown(f"Status: **{result.status.value}**")
if truth["ambiguous_fields"] or truth["conflicts"]:
    st.caption("Ambiguous and conflicting fields are passed on as null (never guessed), so validation reports them "
               "as missing until a planner resolves them.")
if result.issues:
    st.dataframe(pd.DataFrame([i.model_dump(mode="json") for i in result.issues]), hide_index=True, use_container_width=True)
