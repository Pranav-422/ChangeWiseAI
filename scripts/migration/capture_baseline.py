"""Numerical baseline of the real Member 1 and Member 2 engines, one JSON file per scenario.

    python -m scripts.migration.capture_baseline                      write docs/migration/baseline
    python -m scripts.migration.capture_baseline --check <module>     compare another data source with it

<module> is any module with the Member 1 adapter contract plus load_tables(), for example
backend.app.integrations.member1_postgres. No test double is involved.
"""
import argparse
import hashlib
import json
import sys
from importlib import import_module
from pathlib import Path

from member1.engine.bom_impact import generate_bom_impact_report
from member1.engine.data_loader import to_records
from member1.engine.inventory import simulate_from_data
from member1.engine.scenarios import SCENARIOS, load_scenario
from member1.engine.validation import validate_all_inputs
from member3.ai.claim_verifier import build_verified_facts, verify_explanation
from member3.ai.fallback_templates import render_sections
from member3.services.member1_adapter import Member1Adapter
from member3.services.member2_adapter import Member2Adapter
from member3.settings import load_settings

OUT = Path(__file__).resolve().parents[2] / "docs" / "migration" / "baseline"
CSV_MODULE = "member3.integration.member1_module"
CHANGE_ID = "ECN-001"


def plain(value):
    return json.loads(json.dumps(value, default=str))


def capture_scenario(scenario, module, member1, member2):
    tables = load_scenario(scenario, module.load_tables())
    change = next(c for c in to_records(tables["engineering_changes"]) if c["change_id"] == CHANGE_ID)
    dataset = member1.load_dataset(scenario)
    baseline = member1.baseline(dataset)
    result = {**member2.optimize(dataset), "computation_seconds": 0}
    exceptions = member1.exceptions(dataset, baseline)
    bom = member1.bom_impact(change["part_number"])
    facts = build_verified_facts({"run_id": "RUN-BASELINE", "dataset": dataset, "result": result,
                                  "owners": load_settings()["owners"], "baseline": baseline,
                                  "exceptions": exceptions, "bom": bom})
    sections = render_sections(facts)
    return plain({
        "validation": validate_all_inputs(tables, CHANGE_ID),
        "bom_impact": generate_bom_impact_report(change["part_number"], tables["bom"], tables["materials"], change),
        "simulation": simulate_from_data(tables, CHANGE_ID, scenario_id=scenario.upper()),
        "dataset": dataset,
        "baseline": baseline,
        "exceptions": exceptions,
        "optimization": result,
        "configurations": member2.compare(dataset, result),
        "replay_matches": member2.same_result(result, dataset, member2.config),
        "explanation": {"sections": sections, "verification": verify_explanation("\n".join(sections.values()), facts)},
    })


def capture(module_name=CSV_MODULE):
    module = import_module(module_name)
    member1 = Member1Adapter(module_name)
    member2 = Member2Adapter(member1.simulate)
    return {scenario: capture_scenario(scenario, module, member1, member2) for scenario in SCENARIOS}


def differences(expected, actual, path=""):
    """Every leaf that differs, as 'path: expected -> actual'."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = []
        for key in sorted(set(expected) | set(actual)):
            found += differences(expected.get(key), actual.get(key), f"{path}.{key}")
        return found
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return [d for i, (e, a) in enumerate(zip(expected, actual)) for d in differences(e, a, f"{path}[{i}]")]
    return [] if expected == actual else [f"{path}: {str(expected)[:80]} -> {str(actual)[:80]}"]


def write():
    OUT.mkdir(parents=True, exist_ok=True)
    sums = []
    for scenario, content in capture().items():
        data = (json.dumps(content, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()
        (OUT / f"{scenario}.json").write_bytes(data)
        sums.append(f"{hashlib.sha256(data).hexdigest()}  {scenario}.json")
    (OUT / "SHA256SUMS").write_bytes(("\n".join(sums) + "\n").encode())


def check(module_name):
    """{scenario: [differences]} between the stored baseline and the named data source."""
    for line in (OUT / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split()
        if hashlib.sha256((OUT / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"Baseline file {name} was altered.")
    return {scenario: differences(json.loads((OUT / f"{scenario}.json").read_text(encoding="utf-8")), content)
            for scenario, content in capture(module_name).items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", metavar="MODULE")
    args = parser.parse_args()
    if args.check:
        report = check(args.check)
        for name, found in report.items():
            print(f"{name}: {'identical' if not found else f'{len(found)} differences'}")
            for line in found[:20]:
                print("   ", line)
        sys.exit(any(report.values()))
    write()
    print((OUT / "SHA256SUMS").read_text())
