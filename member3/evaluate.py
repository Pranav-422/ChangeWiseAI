"""Measure the AI layer and write member3/reports/ai_validation_report.md, integration_report.md, evidence.json.

    python -m member3.evaluate
    python -m pytest member3 --junitxml=results.xml ; python -m member3.evaluate results.xml   (+ test report)

Uses the configured provider when an API key is set, otherwise the offline rules; the report says which.
"""
import json
import os
import platform
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from member2.evaluation.run_all import table

from .ai.claim_verifier import REJECTED, VERIFIED, verify_explanation
from .ai.ecn_extractor import FIELDS, OFFLINE, extract_ecn_fields, validate_extracted_ecn
from .ai.fallback_templates import render_sections
from .ai.provider import get_provider
from .ai.what_if_parser import parse_what_if_request
from .application.access_control import User
from .settings import ROOT

REPORTS, DEMO = ROOT / "member3" / "reports", ROOT / "member3" / "data" / "demo"
USER = User("Evaluation", "Planner")


def samples(name):
    return json.loads((DEMO / name).read_text(encoding="utf-8"))


def _same(expected, actual):
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.casefold() == actual.casefold()
    return expected == actual


def extraction_results(member1, provider=None):
    dataset, rows = member1.load_dataset("BASE"), []
    for sample in samples("ecn_samples.json"):
        record = extract_ecn_fields(sample["text"], provider, sample["id"])
        status = validate_extracted_ecn(record, lambda f: member1.validate_ecn(f, dataset))["validation_status"]
        correct = [f for f in FIELDS if _same(sample["expected"][f], record[f])]
        wrong = [f for f in FIELDS if record[f] is not None and f not in correct]
        flagged = {i["field"] for i in record["ambiguous_fields"] + record["conflicts"]}
        rows.append({"id": sample["id"], "title": sample["title"], "correct": len(correct), "wrong": wrong,
                     "abstained": [f for f in FIELDS if record[f] is None and f not in correct],
                     "status": status, "status_ok": status == sample["expected_status"],
                     "flags_ok": set(sample["unclear"]) <= flagged})
    return rows


def what_if_results(member1, provider=None):
    dataset, rows = member1.load_dataset("BASE"), []
    neutral = {"lead_time_delta": 0, "demand_change_percent": 0, "effective_week": None,
               "po_quantity_change": None, "supplier_block": None}
    for sample in samples("what_if_samples.json"):
        parsed = parse_what_if_request(sample["question"], dataset, provider)
        got = parsed["parameters"] and {k: parsed["parameters"][k] for k in neutral}
        expected = sample["parameters"] and {**neutral, **sample["parameters"]}
        rows.append({"question": sample["question"], "expected": sample["status"], "actual": parsed["status"],
                     "correct": parsed["status"] == sample["status"] and got == expected,
                     "wrong_run": parsed["status"] == "OK" and got != expected})
    return rows


def tampered(text, facts):
    """False statements built from true ones: each must be rejected."""
    plan_id = facts["recommended_plan_id"]
    plan = facts["plans"][plan_id]
    r = plan["robustness"]
    blocked = next(s for s, status in facts["suppliers"].items() if status == "BLOCKED")
    good = next(s for s, status in facts["suppliers"].items() if status == "APPROVED")
    loser = next(p for p in facts["plans"] if p != plan_id)
    return {
        "invented amount": f"{text} The excess value is ₹87,654.",
        "amount under the wrong name": f"{text} The excess value is ₹{plan['action_cost'] + 1:,.0f}.",
        "invented shortage": f"{text} The shortage is 4321 units.",
        "invented stock": f"{text} Available stock is 777 units.",
        "invented plan": f"{text} Plan P1 is an alternative.",
        "unknown hash plan": f"{text} PLAN-0000000000 is feasible.",
        "wrong rank": f"{text} {loser} is the highest-ranked plan.",
        "wrong robustness": f"{text} The plan passes {r['zero_shortage_runs']}/{r['total_runs'] + 1} stress runs.",
        "wrong week": f"{text} The effective week is W44.",
        "unknown supplier": f"{text} Supplier S77 can deliver.",
        "blocked called approved": f"{text} Supplier {blocked} is approved.",
        "approved called blocked": f"{text} Supplier {good} is blocked.",
        "unknown order": f"{text} PO-999 is reduced.",
        "action on the wrong order": f"{text} Reduce PO-003 by 50.",
        "wrong action amount": f"{text} Reduce PO-001 by 350.",
        "unknown material": f"{text} BRK-Z is affected.",
        "other change": f"{text} This belongs to ECN-9999.",
        "claims approval": f"{text} The plan has been approved.",
        "promises savings": f"{text} This guarantees savings.",
        "claims execution": f"{text} The order has been cancelled.",
        "feasible plan called rule-breaking": f"{text} {plan_id} violates the lead-time rule.",
        "bare number": f"{text} Roughly 5150 are affected.",
        "warning removed": text.replace("Near-tie", "Note").replace("near-tie", "note"),
    }


def build_facts(member1, member2, scenario):
    from .ai.claim_verifier import build_verified_facts
    from .settings import load_settings
    dataset = member1.load_dataset(scenario)
    baseline = member1.baseline(dataset)
    return build_verified_facts({
        "run_id": "RUN-EVAL", "dataset": dataset, "result": member2.optimize(dataset), "baseline": baseline,
        "exceptions": member1.exceptions(dataset, baseline), "owners": load_settings()["owners"],
        "bom": member1.bom_impact(dataset["engineering_change"]["old_material_id"])})


def verifier_results(member1, member2):
    facts = build_facts(member1, member2, "BASE")
    text = "\n".join(render_sections(facts).values())
    attacks = [{"attack": name, "caught": verify_explanation(bad, facts)["status"] == REJECTED}
               for name, bad in tampered(text, facts).items()]
    clean = []
    for scenario in member1.list_scenarios():
        f = build_facts(member1, member2, scenario)
        clean.append({"scenario": scenario,
                      "verified": verify_explanation("\n".join(render_sections(f).values()), f)["status"] == VERIFIED})
    return attacks, clean


def integration_results(member1, member2):
    """Every scenario through the real services on a throwaway database."""
    from .services import approval_service, audit_service, ecn_service, planning_service
    text, rows = samples("ecn_samples.json")[0]["text"], []
    for scenario in member1.list_scenarios():
        review = ecn_service.create_review(text, scenario, member1, USER, source="evaluation")
        row = {"scenario": scenario, "ecn": ecn_service.get_review(review)["validation"]["validation_status"],
               "decision": "not planned", "label": "-", "replay": "-", "approval": "-"}
        rows.append(row)
        try:
            ecn_service.confirm(review, member1, USER)
        except ecn_service.NotReady:
            continue
        run = planning_service.get_run(planning_service.run_planning(review, member1, member2, USER))
        row.update(decision=run["decision"], label=run["explanation"]["label"],
                   replay=audit_service.replay(run["run_id"], member2, USER)["matches"])
        try:
            approval_service.decide(run["run_id"], "APPROVED", USER, member1, member2, "evaluation",
                                    run["result"]["recommended_plan_id"])
            row["approval"] = "recorded"
        except approval_service.DecisionRefused as error:
            row["approval"] = f"refused: {error}"
    return rows, audit_service.verify_chain() is None


def ratio(passed, total):
    return f"{passed}/{total} ({passed / total:.1%})"


def write_test_report(junit_path):
    """application_test_report.md from a real pytest run."""
    counts = {}
    for case in ET.parse(junit_path).iter("testcase"):
        tags = {child.tag for child in case}
        outcome = "failed" if tags & {"failure", "error"} else "skipped" if "skipped" in tags else "passed"
        counts.setdefault(case.get("classname").split(".")[-1], Counter())[outcome] += 1
    total = sum(counts.values(), Counter())
    lines = ["# Application test report",
             f"Generated by `python -m member3.evaluate` from pytest results. Python {platform.python_version()} on "
             f"{platform.system()}. LLM calls are tested with a fake provider; no live LLM was called.",
             table(["Test file", "Passed", "Failed", "Skipped"],
                   [[name, c["passed"], c["failed"], c["skipped"]] for name, c in sorted(counts.items())]
                   + [["**Total**", total["passed"], total["failed"], total["skipped"]]])]
    (REPORTS / "application_test_report.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(junit_path=None):
    if junit_path:
        write_test_report(junit_path)
    from .services.member1_adapter import Member1Adapter
    from .services.member2_adapter import Member2Adapter
    os.environ["CHANGEWISE_DB"] = str(Path(tempfile.mkdtemp()) / "evaluation.db")
    member1 = Member1Adapter()
    member2 = Member2Adapter(member1.simulate)
    provider = get_provider()
    source = provider.name if provider else OFFLINE
    ecn, what_if = extraction_results(member1, provider), what_if_results(member1, provider)
    attacks, clean = verifier_results(member1, member2)
    rows, chain = integration_results(member1, member2)

    total = len(ecn) * len(FIELDS)
    fields_ok, wrong = sum(r["correct"] for r in ecn), sum(len(r["wrong"]) for r in ecn)
    mapped, misrun = sum(r["correct"] for r in what_if), sum(r["wrong_run"] for r in what_if)
    caught = sum(a["caught"] for a in attacks)
    note = (f"Generated by `python -m member3.evaluate`. Source measured: **{source}**. "
            + ("The LLM path was not measured because no API key is configured. The samples were written together "
               "with the offline rules, so this is not an estimate for unseen documents." if not provider else
               "Samples are synthetic."))
    report = ["# AI validation report", note, "## Summary", table(["Measure", "Result"], [
        ["ECN fields correct (value, or correctly left empty)", ratio(fields_ok, total)],
        ["ECN fields filled with a wrong value", wrong],
        ["ECN validation status as expected", ratio(sum(r["status_ok"] for r in ecn), len(ecn))],
        ["Ambiguity and conflict flags as expected", ratio(sum(r["flags_ok"] for r in ecn), len(ecn))],
        ["What-if requests mapped correctly", ratio(mapped, len(what_if))],
        ["What-if requests run with wrong parameters", misrun],
        ["False statements rejected by the claim verifier", ratio(caught, len(attacks))],
        ["Template explanations that pass the verifier", ratio(sum(c["verified"] for c in clean), len(clean))],
        ["LLM claims verified", "not measured (no LLM run)" if not provider else "see planning runs"]]),
        "## ECN samples", table(["Sample", "Title", "Correct fields", "Left empty but present", "Wrong", "Status"],
                                [[r["id"], r["title"], f"{r['correct']}/{len(FIELDS)}", ", ".join(r["abstained"]) or "-",
                                  ", ".join(r["wrong"]) or "-", r["status"] + ("" if r["status_ok"] else " (unexpected)")]
                                 for r in ecn]),
        "## What-if samples", table(["Question", "Expected", "Actual", "Correct"],
                                    [[r["question"], r["expected"], r["actual"], r["correct"]] for r in what_if]),
        "## Claim verifier attacks", table(["False statement", "Rejected"], [[a["attack"], a["caught"]] for a in attacks])]
    (REPORTS / "ai_validation_report.md").write_text("\n\n".join(report) + "\n", encoding="utf-8", newline="\n")
    integration = ["# Integration report", f"Generated by `python -m member3.evaluate`. Member 1 module: `{member1.name}`"
                   f"{' (temporary stand-in)' if member1.synthetic else ''}. Member 2: `member2.engine.pipeline`.",
                   "Each scenario runs through the services with the same ECN text: intake, confirmation, planning, "
                   "explanation, replay, approval.",
                   table(["Scenario", "ECN", "Planning decision", "Explanation", "Replay identical", "Approval"],
                         [list(r.values()) for r in rows]),
                   f"Audit chain intact: {chain}."]
    (REPORTS / "integration_report.md").write_text("\n\n".join(integration) + "\n", encoding="utf-8", newline="\n")
    evidence = {"ecn_field_extraction_accuracy": {"value": round(fields_ok / total, 4), "evidence": f"{source}, {len(ecn)} synthetic samples"},
                "what_if_mapping_accuracy": {"value": round(mapped / len(what_if), 4), "evidence": f"{source}, {len(what_if)} synthetic questions"}}
    (REPORTS / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("\n\n".join(report[2:4]))
    print("\n\n".join(integration[3:]))


if __name__ == "__main__":
    main(*sys.argv[1:2])
