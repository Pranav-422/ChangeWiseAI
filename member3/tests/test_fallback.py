import json

import pytest
from jsonschema import Draft202012Validator

from member3.ai.explanation_generator import AI_VERIFIED, AWAITING_REVIEW, TEMPLATE, generate_explanation
from member3.ai.fallback_templates import render_sections
from member3.ai.provider import ProviderError
from member3.evaluate import build_facts
from member3.settings import ROOT
from .conftest import FakeProvider

SCHEMA = Draft202012Validator(json.loads((ROOT / "member3/contracts/explanation_schema.json").read_text(encoding="utf-8")))


def explain(facts, reply):
    record = generate_explanation(facts, FakeProvider(reply))
    SCHEMA.validate(json.loads(json.dumps(record)))
    return record


def test_no_provider_uses_templates(facts):
    record = generate_explanation(facts)
    assert record["label"] == TEMPLATE and record["sections"] == render_sections(facts) and record["warning"] is None


@pytest.mark.parametrize("reply", [
    ProviderError("timeout"), {}, {"sections": []}, {"sections": {}}, {"sections": {"Invented": "x"}},
    {"sections": {"Risks": 5}}, {"sections": {"Risks": " "}}])
def test_provider_problems_use_templates(facts, reply):
    record = explain(facts, reply)
    assert record["label"] == TEMPLATE and "unavailable" in record["warning"]


def test_verified_ai_text_is_shown(facts):
    sections = render_sections(facts)
    record = explain(facts, {"sections": sections})
    assert record["label"] == AI_VERIFIED and record["sections"] == sections and record["source"] == "fake"


def test_unsupported_ai_text_is_hidden_and_kept(facts):
    sections = {**render_sections(facts), "Risks": "A fine of ₹9,99,999 applies."}
    record = explain(facts, {"sections": sections})
    assert record["label"] == TEMPLATE and record["sections"] == render_sections(facts)
    assert record["rejected_draft"]["Risks"].startswith("A fine") and record["verification"]["failures"]
    assert "not shown" in record["warning"]


def test_uncheckable_ai_text_is_separated(facts):
    sections = {**render_sections(facts), "Risks": "Supplier S1 is unreliable."}
    record = explain(facts, {"sections": sections})
    assert record["label"] == AWAITING_REVIEW and record["draft"]["Risks"] == "Supplier S1 is unreliable."
    assert record["sections"] == render_sections(facts)


@pytest.mark.parametrize("scenario,section,words", [
    ("BASE", "Robustness", "Near-tie"), ("REV_C_DELAY", "Inventory impact", "shortage is 300 units, in W6, W7, W8"),
    ("REV_C_SUPPLIER_BLOCKED", "Recommendation", "No feasible plan"),
    ("REV_C_SUPPLIER_BLOCKED", "Risks", "Supplier S1 is blocked"),
    ("MISSING_RECORD", "Recommendation", "invalid or conflicting"),
    ("REV_C_DELAY_NO_EXPEDITE", "Recommendation", "still leaves a shortage of 100 units"),
    ("BASE", "Planner decision", "Purchasing, Quality")])
def test_templates_state_the_engine_result(member1, member2, scenario, section, words):
    assert words in render_sections(build_facts(member1, member2, scenario))[section]


def test_no_placeholder_text(member1, member2):
    for scenario in member1.list_scenarios():
        text = " ".join(render_sections(build_facts(member1, member2, scenario)).values())
        assert "None" not in text and "{" not in text and "nan" not in text
