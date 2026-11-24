"""The application on Member 1's real module and Member 2's real engine."""
import pytest
from streamlit.testing.v1 import AppTest

from member1.engine.bom_impact import generate_bom_impact_report
from member1.engine.data_loader import load_csv_data
from member1.engine.inventory import simulate_from_data
from member1.engine.scenarios import load_scenario
from member3.ai.claim_verifier import REJECTED, VERIFIED, verify_explanation
from member3.ai.ecn_extractor import extract_ecn_fields
from member3.ai.fallback_templates import render_sections
from member3.ai.what_if_parser import CLARIFY, OK, parse_what_if_request
from member3.application.navigation import PAGES, PAGES_DIR
from member3.evaluate import build_facts, member1_pdf_results, tampered
from member3.services import action_tracker_service as tracker
from member3.services import audit_service, ecn_service, planning_service, what_if_service
from member3.services.approval_service import decide
from member3.services.member1_adapter import Member1Adapter
from member3.services.member2_adapter import Member2Adapter
from .conftest import PLANNER

REAL = "member3.integration.member1_module"
SCENARIOS = ("base", "rev_c_supplier_delay", "excess_rev_b_orders", "blocked_supplier", "date_conflict", "missing_records")


@pytest.fixture(scope="module")
def real():
    member1 = Member1Adapter(REAL)
    return member1, Member2Adapter(member1.simulate)


@pytest.fixture(scope="module")
def ecn001(real):
    return next(s["text"] for s in real[0].sample_documents() if s["id"] == "ECN-001")


@pytest.fixture
def plan(real, ecn001):
    def make(scenario="base"):
        review = ecn_service.create_review(ecn001, scenario, real[0], PLANNER)
        ecn_service.confirm(review, real[0], PLANNER)
        return planning_service.get_run(planning_service.run_planning(review, *real, PLANNER))
    return make


def test_scenarios_come_from_member1(real):
    assert tuple(real[0].list_scenarios()) == SCENARIOS


def test_pdfs_are_never_filled_with_a_wrong_value(real):
    score = member1_pdf_results()
    assert score["fields_scored"] == 180
    assert [e for e in score["errors"] if e["got"] is not None] == []


def test_only_the_matching_document_can_be_confirmed(real):
    """18 documents, one of them describes this dataset's change record."""
    confirmable = []
    for sample in real[0].sample_documents():
        review = ecn_service.create_review(sample["text"], "base", real[0], PLANNER, source=sample["id"])
        if ecn_service.get_review(review)["validation"]["validation_status"] == "VALID":
            confirmable.append(sample["id"])
    assert confirmable == ["ECN-001"]


def test_member1_validation_is_used(real, ecn001):
    data = real[0].load_dataset("base")
    fields = extract_ecn_fields(ecn001.replace("MAT-101", "MAT-999"))
    codes = {e["code"] for e in real[0].validate_ecn(fields, data)}
    assert "ECN_UNKNOWN_PART" in codes
    assert real[0].validate_ecn(extract_ecn_fields(ecn001), data) == []


def test_bom_is_member1s(real):
    impact = real[0].bom_impact("MAT-101")
    tables = load_csv_data()
    report = generate_bom_impact_report("MAT-101", tables["bom"], tables["materials"])
    assert impact["finished_assemblies"] == report["affected_finished_products"] == ["KIT-301", "PUMP-001", "PUMP-002"]
    assert ["MAT-101", "SUB-201", "PUMP-001"] in impact["paths"]


@pytest.mark.parametrize("scenario", ["base", "rev_c_supplier_delay", "excess_rev_b_orders", "blocked_supplier"])
def test_exceptions_keep_member1s_order_and_score(real, scenario):
    data = real[0].load_dataset(scenario)
    mine = real[0].exceptions(data, real[0].baseline(data))
    own = simulate_from_data(load_scenario(scenario), "ECN-001")["exceptions"]
    assert [(e["type"], e["severity"]) for e in mine] == [(e["exception_type"], e["severity_score"]) for e in own]


def test_full_flow(real, plan):
    run = plan()
    best = run["result"]["recommendations"][0]
    assert run["result"]["simulator"] == "member2.integration.member1_bridge:simulate_inventory"
    assert best["summary"] == "Reduce PO-001 by 200" and best["secondary_cost"] == 17000
    decide(run["run_id"], "APPROVED", PLANNER, *real, "ok", plan_id=best["plan_id"])
    for item in tracker.list_items(run["run_id"]):
        tracker.advance(item["action_id"], PLANNER)
        tracker.advance(item["action_id"], PLANNER)
    tracker.close_change(run["run_id"], PLANNER)
    assert planning_service.change_stage("base") == 5
    assert audit_service.replay(run["run_id"], real[1], PLANNER)["matches"]
    assert audit_service.verify_chain() is None


@pytest.mark.parametrize("scenario", ["date_conflict"])
def test_record_conflict_blocks_confirmation(real, ecn001, scenario):
    review = ecn_service.create_review(ecn001, scenario, real[0], PLANNER)
    with pytest.raises(ecn_service.NotReady):
        ecn_service.confirm(review, real[0], PLANNER)


@pytest.mark.parametrize("scenario,decision", [
    ("blocked_supplier", "NO_FEASIBLE_PLAN"), ("missing_records", "INVALID_DATA"), ("excess_rev_b_orders", "RECOMMENDED")])
def test_other_decisions(plan, scenario, decision):
    assert plan(scenario)["decision"] == decision


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_templates_pass_the_verifier(real, scenario):
    facts = build_facts(*real, scenario)
    text = "\n".join(render_sections(facts).values())
    result = verify_explanation(text, facts)
    assert result["status"] == VERIFIED, result
    assert "None" not in text and "nan" not in text


def test_false_statements_are_rejected(real):
    facts = build_facts(*real, "base")
    for name, text in tampered("\n".join(render_sections(facts).values()), facts).items():
        assert verify_explanation(text, facts)["status"] == REJECTED, name


def ask(real, run, question):
    parsed = parse_what_if_request(question, run["dataset"])
    assert parsed["status"] == OK, parsed
    return what_if_service.submit_scenario_to_optimizer(parsed["parameters"], run, real[1], PLANNER, question)


def test_what_if(real, plan):
    run = plan()
    late = ask(real, run, "What if the Rev C supplier is delayed by one week?")
    # Order W2 + expedited lead 3 + 1 week late = W6, so the paid expedite just saves W6.
    assert late["plan"]["summary"].startswith("Expedite PO-003 by 1 wk") and late["plan"]["secondary_cost"] == 29000
    later = ask(real, run, "What if the Rev C supplier is delayed by two weeks?")
    assert later["plan"]["shortage_units"] == 150           # W7 at best; Rev B ended in W5
    week7 = ask(real, run, "What if we shift the effective date to W7?")
    assert week7["plan"]["shortage_units"] == 150
    cut = ask(real, run, "Reduce PO-002 by 50 units")
    assert "Reduce PO-002 by 50" in cut["plan"]["summary"]
    blocked = ask(real, run, "What if supplier S2 becomes blocked?")
    assert blocked["result"]["decision"] == "NO_FEASIBLE_PLAN"


def test_two_open_rev_b_orders_need_a_name(plan):
    parsed = parse_what_if_request("Reduce the Rev B purchase order by 100 units", plan()["dataset"])
    assert parsed["status"] == CLARIFY and "PO-001, PO-002" in parsed["message"]


@pytest.mark.parametrize("file", [p[0] for p in PAGES])
@pytest.mark.parametrize("scenario", ["base", "missing_records"])
def test_pages(monkeypatch, plan, file, scenario):
    monkeypatch.setenv("CHANGEWISE_MEMBER1", REAL)
    plan(scenario)
    app = AppTest.from_file(str(PAGES_DIR / file), default_timeout=60)
    app.session_state["scenario"] = scenario
    app.run()
    assert not app.exception
