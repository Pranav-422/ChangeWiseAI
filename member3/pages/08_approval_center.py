import pandas as pd
import streamlit as st

from member3.application.session_manager import context, page_header, require_run
from member3.components import approval_panel, explanation_panel
from member3.services import approval_service

ctx = context()
page_header("Approval Center", ctx)
waiting = approval_service.pending_runs()
if waiting:
    st.markdown("**Waiting for a decision**")
    st.dataframe(pd.DataFrame(waiting), hide_index=True)
run = require_run(ctx)
st.subheader(f"{ctx.scenario}: {run['run_id']}")
approval_panel.render(ctx)
with st.expander("Explanation"):
    explanation_panel.render(run["explanation"])
