import streamlit as st

from ..services.planning_service import STAGES


def render(done):
    st.markdown(" → ".join(f":green-badge[✓ {s}]" if i < done else f":gray-badge[{s}]" for i, s in enumerate(STAGES)))
