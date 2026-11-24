import json

import pandas as pd
import streamlit as st


def render(events):
    if not events:
        st.info("No events yet.")
        return
    st.dataframe(pd.DataFrame([{
        "#": e["seq"], "Time (UTC)": e["created_at"], "Event": e["event_type"].replace("_", " ").capitalize(),
        "Record": e["entity_id"], "User": e["user_name"], "Role": e["role"],
        "Details": json.dumps(e["payload"], ensure_ascii=False), "Hash": e["event_hash"][:12],
    } for e in events]), hide_index=True)
