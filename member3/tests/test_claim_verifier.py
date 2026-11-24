import pytest

from member3.ai.claim_verifier import REJECTED, REVIEW, VERIFIED, extract_explanation_claims, verify_explanation
from member3.ai.fallback_templates import render_sections
from member3.evaluate import build_facts, tampered

ATTACKS = ["invented amount", "amount under the wrong name", "invented shortage", "invented stock", "invented plan",
           "unknown hash plan", "wrong rank", "wrong robustness", "wrong week", "unknown supplier",
           "blocked called approved", "approved called blocked", "unknown order", "action on the wrong order",
           "wrong action amount", "unknown material", "other change", "claims approval", "promises savings",
           "claims execution", "feasible plan called rule-breaking", "bare number", "warning removed"]


def text(facts):
    return "\n".join(render_sections(facts).values())


@pytest.mark.parametrize("scenario", [
    "BASE", "REV_C_DELAY", "REV_C_DELAY_NO_EXPEDITE", "EXCESS_REV_B", "REV_C_SUPPLIER_BLOCKED",
    "ALTERNATE_SUPPLIER", "UNAUTHORIZED_GROUP", "DATE_CONFLICT", "MISSING_RECORD"])
def test_true_text_is_verified(member1, member2, scenario):
    facts = build_facts(member1, member2, scenario)
    result = verify_explanation(text(facts), facts)
    assert result["status"] == VERIFIED, result


@pytest.mark.parametrize("name", ATTACKS)
def test_false_text_is_rejected(facts, name):
    attacks = tampered(text(facts), facts)
    assert set(attacks) == set(ATTACKS)
    assert verify_explanation(attacks[name], facts)["status"] == REJECTED


@pytest.mark.parametrize("sentence", [
    "Supplier S1 is unreliable.", "The shortage happens because the supplier is slow.", "Quality looks good.",
    "This could fail.", "Three hundred units are exposed."])
def test_uncheckable_text_waits_for_review(facts, sentence):
    result = verify_explanation(f"{text(facts)} {sentence}", facts)
    assert result["status"] == REVIEW and sentence in result["needs_review"]


def test_free_wording_of_true_facts_is_verified(facts):
    best = facts["recommended_plan_id"]
    draft = (f"ECN-1001 replaces BRK-B with BRK-C in W6. {best} is the highest-ranked plan. "
             f"It has a shortage of 0 units, an excess value of ₹0 and an action cost of Rs. 1,250. "
             f"{best} passes 8 of 9 stress runs. Supplier S3 is blocked. "
             "This is a near-tie, so the planner must review it.")
    result = verify_explanation(draft, facts)
    assert result["status"] == VERIFIED, result


def test_alternative_plan_is_checked_against_its_own_numbers(facts):
    other = next(p for p, v in facts["plans"].items() if v["rank"] == 2)
    cost = facts["plans"][other]["action_cost"]
    assert verify_explanation(f"{text(facts)} {other} has an action cost of ₹{cost}.", facts)["status"] == VERIFIED
    assert verify_explanation(f"{text(facts)} {other} has an action cost of ₹1,250.", facts)["status"] == REJECTED


def test_approval_claim_is_allowed_once_true(facts):
    draft = text({**facts, "approved": True}) + " The plan has been approved."
    assert verify_explanation(draft, facts)["status"] == REJECTED
    assert verify_explanation(draft, {**facts, "approved": True})["status"] != REJECTED


def test_residual_shortage_must_be_mentioned(member1, member2):
    facts = build_facts(member1, member2, "REV_C_DELAY_NO_EXPEDITE")
    assert verify_explanation("The planner must review this case.", facts)["failures"][0]["detail"] == "RESIDUAL_SHORTAGE"
    assert verify_explanation(text(facts) + " The plan has no shortage.", facts)["status"] == REJECTED


def test_empty_text_is_rejected(facts):
    assert verify_explanation("", facts)["status"] == REJECTED


def test_claims_are_split_by_kind():
    claim = extract_explanation_claims("PLAN-12ab34cd56 cuts PO-001 to ₹1,00,000 and 50 units in W7, 8/9 runs, 10%.")[0]
    assert claim["plans"] == ["PLAN-12ab34cd56"] and claim["orders"] == ["PO-001"] and claim["weeks"] == [7]
    assert [m["value"] for m in claim["money"]] == [100000] and [u["value"] for u in claim["units"]] == [50]
    assert claim["ratios"][0]["value"] == (8, 9) and claim["percents"][0]["value"] == 10 and claim["numbers"] == []
