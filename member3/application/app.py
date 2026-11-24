"""ChangeWise AI application.

    streamlit run member3/application/app.py        (from the repository root)
"""
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)  # streamlit runs this file as a script

import streamlit as st  # noqa: E402

from member3.application import navigation, session_manager  # noqa: E402
from member3.settings import load_settings  # noqa: E402

st.set_page_config(page_title=load_settings()["application"]["title"], layout="wide")
page = navigation.build()
session_manager.render_sidebar()
page.run()
