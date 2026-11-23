from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from .helpers import SCENARIOS

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_renders(name):
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.sidebar.selectbox[0].set_value(name).run()
    assert not app.exception
