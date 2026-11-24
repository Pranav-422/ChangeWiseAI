from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from member2.integration.member1_bridge import list_scenarios

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


@pytest.mark.parametrize("name", list_scenarios())
def test_every_scenario_renders(name):
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.sidebar.selectbox[0].set_value(name).run()
    assert not app.exception
