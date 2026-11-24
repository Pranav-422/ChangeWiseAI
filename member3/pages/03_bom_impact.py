import pandas as pd
import streamlit as st

from member3.application.session_manager import context, page_header
from member3.components import bom_tree, kpi_cards

ctx = context()
page_header("BOM Impact Analysis", ctx)
change = ctx.dataset["engineering_change"]
impact = ctx.member1.bom_impact(change["old_material_id"])
revision = {m["material_id"]: m["revision"] for m in ctx.dataset["materials"]}
kpi_cards.render([
    ("Changed material", impact["material_id"], None),
    ("Old revision", revision.get(change["old_material_id"]), None),
    ("New revision", revision.get(change["new_material_id"]), change["new_material_id"]),
    ("Impact status", impact["impact_status"].replace("_", " ").capitalize(), None),
])
left, right = st.columns(2)
with left:
    bom_tree.render(impact)
with right:
    for title, key in (("Direct parents", "direct_parents"), ("Indirect parents", "indirect_parents"),
                       ("Finished assemblies", "finished_assemblies")):
        st.markdown(f"**{title}:** {', '.join(impact[key]) or 'none'}")
    st.markdown("**Where-used paths**")
    st.dataframe(pd.DataFrame([{"Finished assembly": p[-1], "Path": " → ".join(p), "Levels": len(p) - 1}
                               for p in impact["paths"]]), hide_index=True)
