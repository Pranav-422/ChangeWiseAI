import pandas as pd
import streamlit as st

_LABEL = {"AI_GENERATED_VERIFIED": ":green-badge[✓ AI-generated and verified]",
          "TEMPLATE_GENERATED": ":blue-badge[Template-generated]",
          "AWAITING_REVIEW": ":orange-badge[Awaiting review]"}


def _sections(sections):
    for title, text in sections.items():
        st.markdown(f"**{title}**")
        st.text(text)  # plain text: document or model wording is never rendered as markup


def render(explanation):
    st.markdown(_LABEL[explanation["label"]])
    if explanation["warning"]:
        st.warning(explanation["warning"])
    if explanation["draft"]:
        with st.expander("AI draft awaiting review"):
            _sections(explanation["draft"])
            st.caption("Check these sentences: " + " | ".join(explanation["verification"]["needs_review"]))
    _sections(explanation["sections"])
    failures = (explanation["verification"] or {}).get("failures")
    if failures:
        with st.expander(f"Failed verification ({len(failures)} claims)"):
            st.dataframe(pd.DataFrame(failures), hide_index=True)
