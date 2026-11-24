"""The nine pages, in menu order."""
from pathlib import Path

import streamlit as st

PAGES_DIR = Path(__file__).resolve().parents[1] / "pages"
PAGES = (
    ("01_dashboard.py", "Executive Dashboard", ":material/dashboard:"),
    ("02_ecn_intake.py", "ECN Intake", ":material/upload_file:"),
    ("03_bom_impact.py", "BOM Impact Analysis", ":material/account_tree:"),
    ("04_inventory_monitor.py", "Inventory Monitor", ":material/inventory_2:"),
    ("05_optimization.py", "Optimization Recommendations", ":material/tune:"),
    ("06_what_if.py", "What-If Simulator", ":material/help:"),
    ("07_action_tracker.py", "Action Tracker", ":material/checklist:"),
    ("08_approval_center.py", "Approval Center", ":material/approval:"),
    ("09_audit_history.py", "Audit History", ":material/history:"),
)


def build():
    return st.navigation([
        st.Page(PAGES_DIR / file, title=title, icon=icon, url_path=file[3:-3], default=i == 0)
        for i, (file, title, icon) in enumerate(PAGES)])
