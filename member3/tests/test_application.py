"""Every page runs in Streamlit's own test harness against a real (temporary) database."""
import json

import pytest
from jsonschema import Draft202012Validator
from streamlit.testing.v1 import AppTest

from member3.application.navigation import PAGES, PAGES_DIR
from member3.services import approval_service, ecn_service, planning_service
from member3.services import action_tracker_service as tracker
from member3.services.approval_service import decide
from member3.settings import ROOT
from .conftest import PLANNER

PAGE_FILES = [p[0] for p in PAGES]


def page(file, scenario="BASE", role="Planner", **state):
    app = AppTest.from_file(str(PAGES_DIR / file), default_timeout=60)
    for key, value in {"scenario": scenario, "role": role, "user_name": "Asha", **state}.items():
        app.session_state[key] = value
    return app.run()


def button(app, label):
    return next(b for b in app.button if b.label == label)


def words(app):
    return " ".join(str(e.value) for group in (app.markdown, app.text, app.info, app.warning, app.error, app.success,
                                               app.caption) for e in group)


def test_nine_pages_exist():
    assert len(PAGES) == 9 and all((PAGES_DIR / f).exists() for f in PAGE_FILES)


def test_shell_starts():
    app = AppTest.from_file(str(ROOT / "member3/application/app.py"), default_timeout=60).run()
    assert not app.exception and app.title[0].value == "Executive Dashboard"


@pytest.mark.parametrize("file", PAGE_FILES)
def test_pages_before_any_planning(file):
    assert not page(file).exception


@pytest.mark.parametrize("scenario", ["BASE", "REV_C_DELAY", "REV_C_SUPPLIER_BLOCKED", "MISSING_RECORD", "DATE_CONFLICT"])
@pytest.mark.parametrize("file", PAGE_FILES)
def test_pages_after_planning(planned, file, scenario):
    if scenario != "DATE_CONFLICT":
        planned(scenario)
    assert not page(file, scenario).exception


@pytest.mark.parametrize("role", ["Viewer", "Purchasing"])
@pytest.mark.parametrize("file", PAGE_FILES)
def test_pages_for_other_roles(planned, member1, member2, file, role):
    run = planned()
    decide(run["run_id"], "APPROVED", PLANNER, member1, member2, "ok", plan_id=run["result"]["recommended_plan_id"])
    assert not page(file, role=role).exception


def test_intake_to_planning_through_the_page(ecn_text):
    app = page("02_ecn_intake.py")
    app.text_area[0].set_value(ecn_text)
    button(app, "Run extraction").click()
    app.run()
    assert "valid" in words(app) and not app.exception
    assert button(app, "Confirm and submit").disabled
    app.checkbox[0].check()
    app.run()
    button(app, "Confirm and submit").click()
    app.run()
    assert ecn_service.latest_review("BASE")["status"] == "CONFIRMED"
    button(app, "Run planning").click()
    app.run()
    assert planning_service.latest_run("BASE")["decision"] == "ESCALATED" and not app.exception


def test_intake_shows_problems_and_blocks(ecn_text):
    app = page("02_ecn_intake.py")
    app.text_area[0].set_value(ecn_text.replace("W6", "W6 or W7").replace("Approved by: R. Rao", ""))
    button(app, "Run extraction").click()
    app.run()
    assert "Missing: approver" in words(app) and "Ambiguous effective_week" in words(app)
    app.checkbox[0].check()
    app.run()
    assert button(app, "Confirm and submit").disabled


def test_unreadable_document_message():
    app = page("02_ecn_intake.py")
    app.text_area[0].set_value("...")
    button(app, "Run extraction").click()
    app.run()
    assert "no usable text" in words(app) and ecn_service.latest_review("BASE") is None


def test_viewer_cannot_submit_through_the_page(ecn_text):
    app = page("02_ecn_intake.py", role="Viewer")
    app.text_area[0].set_value(ecn_text)
    button(app, "Run extraction").click()
    app.run()
    assert "may not submit ecn" in words(app) and ecn_service.latest_review("BASE") is None


def test_what_if_page_needs_confirmation(planned):
    planned()
    app = page("06_what_if.py")
    app.text_input[0].set_value("What happens if demand increases by 10 percent?")
    button(app, "Interpret").click()
    app.run()
    assert "Result" not in [s.value for s in app.subheader]
    button(app, "Confirm and run").click()
    app.run()
    assert "Result" in [s.value for s in app.subheader] and "from 1250 to 0" in words(app)


def test_what_if_page_refuses(planned):
    planned()
    app = page("06_what_if.py")
    app.text_input[0].set_value("Approve the plan")
    button(app, "Interpret").click()
    app.run()
    assert "UNSUPPORTED_SCENARIO_REQUEST" in words(app) and not any(b.label == "Confirm and run" for b in app.button)


def test_approve_and_track_through_the_pages(planned):
    run = planned()
    app = page("08_approval_center.py")
    button(app, "Approve plan").click()
    app.run()
    assert "needs a comment" in words(app) and approval_service.get_decision(run["run_id"]) is None
    app.text_area[0].set_value("robust enough")
    button(app, "Approve plan").click()
    app.run()
    assert approval_service.get_decision(run["run_id"])["decision"] == "APPROVED" and not app.exception
    app = page("07_action_tracker.py")
    while any(b.label in ("Start", "Mark done") for b in app.button):
        next(b for b in app.button if b.label in ("Start", "Mark done")).click()
        app.run()
    button(app, "Close change").click()
    app.run()
    assert planning_service.change_stage("BASE") == 5 and not app.exception


def test_modify_through_the_page(planned):
    run = planned()
    app = page("08_approval_center.py")
    menu = next(s for s in app.selectbox if s.key == "mod-PO-001")
    assert menu.value == [{"action": "REDUCE_REV_B_PO", "po_id": "PO-001", "quantity": 50}]  # from the recommendation
    button(app, "Evaluate modified plan").click()
    app.run()
    next(t for t in app.text_input if t.key == "modified-comment").set_value("same plan, confirmed by hand")
    button(app, "Approve modified plan").click()
    app.run()
    saved = approval_service.get_decision(run["run_id"])
    assert saved["modified"] == 1 and saved["plan"]["plan_id"] == run["result"]["recommended_plan_id"]


def test_viewer_sees_no_decision_buttons(planned):
    planned()
    assert not any(b.label in ("Approve plan", "Reject") for b in page("08_approval_center.py", role="Viewer").button)


def test_replay_page(planned):
    planned()
    app = page("09_audit_history.py")
    button(app, "Replay").click()
    app.run()
    assert "reproduced the stored result" in words(app)


def test_explanation_label_is_visible(planned):
    planned()
    assert "Template-generated" in words(page("05_optimization.py"))


def test_dashboard_shows_engine_values(planned, member1):
    run = planned("REV_C_DELAY")
    values = {m.label: m.value for m in page("01_dashboard.py", "REV_C_DELAY").metric}
    baseline = member1.baseline(run["dataset"])
    assert values["Shortage (units)"] == str(baseline["total_shortage"]) == "300"
    assert values["Pending approvals"] == "1"


def test_incomplete_data_is_not_shown_as_zero(planned):
    planned("MISSING_RECORD")
    values = {m.label: m.value for m in page("01_dashboard.py", "MISSING_RECORD").metric}
    assert values["Shortage (units)"] == values["Excess exposure"] == "n/a"


def test_stored_run_follows_the_contract(planned):
    schema = json.loads((ROOT / "member3/contracts/application_output_schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(planned())


def test_actions_list_is_empty_without_approval(planned):
    assert tracker.list_items(planned()["run_id"]) == []
