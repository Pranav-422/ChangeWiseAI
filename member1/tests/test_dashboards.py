"""Each Streamlit view must render without raising (headless AppTest)."""
import pytest
from streamlit.testing.v1 import AppTest

from engine import ROOT


@pytest.mark.parametrize("page", ["inventory_view.py", "bom_view.py", "ecn_intake.py"])
def test_dashboard_renders(page):
    at = AppTest.from_file(str(ROOT / "dashboard" / page), default_timeout=60).run()
    assert not at.exception


def test_inventory_view_reacts_to_lead_time_shock():
    at = AppTest.from_file(str(ROOT / "dashboard" / "inventory_view.py"), default_timeout=60).run()
    at.sidebar.select_slider[0].set_value(2).run()
    assert not at.exception
    assert at.metric[0].value == "300"


def test_inventory_view_handles_change_after_horizon(monkeypatch):
    import engine.scenarios as sc
    original = sc.load_scenario

    def late(name, data=None):
        d = original(name, data)
        d["engineering_changes"]["effective_week"] = 10
        d["engineering_changes"]["use_up_end_week"] = 9
        return d
    monkeypatch.setattr(sc, "load_scenario", late)
    at = AppTest.from_file(str(ROOT / "dashboard" / "inventory_view.py"), default_timeout=60).run()
    assert not at.exception
