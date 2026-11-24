"""Standalone where-used (reverse BOM) view. Run:  streamlit run dashboard/bom_view.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from engine.bom_impact import generate_bom_impact_report  # noqa: E402
from engine.data_loader import load_csv_data, to_records  # noqa: E402

st.set_page_config(page_title="ChangeWise - BOM impact", layout="wide")
st.title("BOM impact (where-used)")
st.caption("Synthetic demo data. Paths are traced from the BOM by the Member 1 engine.")

data = load_csv_data()
mats = {m["material_id"]: m for m in to_records(data["materials"])}
changes = {c["part_number"]: c for c in to_records(data["engineering_changes"])}
components = [m for m, r in mats.items() if r["material_type"] == "COMPONENT"]
material = st.selectbox("Changed material", components, index=components.index("MAT-101"),
                        format_func=lambda m: f"{m} - {mats[m]['material_name']}")
report = generate_bom_impact_report(material, data["bom"], data["materials"], changes.get(material))

c = st.columns(4)
c[0].metric("Impact status", report["impact_status"])
c[1].metric("Direct parents", len(report["direct_parents"]))
c[2].metric("Indirect parents", len(report["indirect_parents"]))
c[3].metric("Affected top-level products", len(report["affected_finished_products"]))
if report.get("change_id"):
    st.info(f"{report['change_id']}: {material} {report['old_revision']} → {report['new_material']} {report['new_revision']}")

if report["affected_assemblies"]:
    # Left-to-right tree: finished products -> assemblies -> changed part (red) -> new revision (green, dashed)
    lines = ['digraph { rankdir=LR; bgcolor="transparent";',
             'node [shape=box style="rounded,filled" fontname=Helvetica fillcolor="#1f4e79" fontcolor=white color="#1f4e79"];',
             'edge [color="#8899aa"];']
    edges = set()
    for a in report["affected_assemblies"]:
        for mid, name in zip(a["path_ids"], a["path"]):
            lines.append(f'"{mid}" [label="{name}\\n{mid}"];')
        edges |= set(zip(a["path_ids"], a["path_ids"][1:]))
    lines += [f'"{p}" -> "{c}";' for p, c in sorted(edges)]
    lines.append(f'"{material}" [fillcolor="#d62728" color="#d62728"];')
    if report.get("new_material"):
        new = report["new_material"]
        lines.append(f'"{new}" [label="{mats.get(new, {}).get("material_name", new)}\\n{new} (new)" '
                     'fillcolor="#2ca02c" color="#2ca02c" style="rounded,filled,dashed"];')
        lines.append(f'"{material}" -> "{new}" [style=dashed color="#2ca02c" label=" replaced by" fontcolor="#2ca02c"];')
    st.graphviz_chart("\n".join(lines + ["}"]), use_container_width=True)
    st.subheader("Complete where-used paths")
    st.dataframe(pd.DataFrame([{"top-level product": a["assembly"], "type": a["assembly_type"],
                                "path": " → ".join(a["path"]), "qty per product": a["quantity_per_assembly"]}
                               for a in report["affected_assemblies"]]), hide_index=True, use_container_width=True)
else:
    st.warning("No assembly uses this material.")
if report["cycles"]:
    st.error(f"BOM cycles detected: {report['cycles']}")
with st.expander("Raw impact report (JSON for Members 2 and 3)"):
    st.json(report)
