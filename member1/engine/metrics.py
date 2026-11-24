"""Member 1 evaluation metrics (deck slide 8), for Member 2's evaluation report to consume.

  bom_impact_completeness      found affected parents / hand-checked affected parents
  inventory_reconciliation     reconciled week-revision balances / all balances, over every scenario x stress run
  shortage_excess_detection    scenarios whose shortage weeks, quantities and scrap match the hand-checked values
  audit_replay                 re-runs that reproduce the same simulation_id and result
  ecn_field_accuracy           field-level extraction accuracy against documents/expected_outputs (for Member 3)
  ranking_agreement            Kendall tau between the engine's severity order and a manually ranked list
"""
import json
from itertools import combinations, product

from . import ROOT
from .bom_impact import get_affected_assemblies
from .inventory import calculate_closing_stock, simulate_from_data
from .scenarios import SCENARIOS, load_scenario

EXPECTED = ROOT / "documents" / "expected_outputs"
STRESS_GRID = list(product([0, 1, 2], [0.9, 1.0, 1.1]))     # the 9 robustness scenarios


def _expected() -> dict:
    return json.loads((EXPECTED / "simulation_expected.json").read_text(encoding="utf-8"))


def bom_impact_completeness(data) -> dict:
    out = {}
    for material, truth in _expected()["bom_impact"].items():
        a = get_affected_assemblies(material, data["bom"])
        found = set(a["direct_parents"]) | set(a["indirect_parents"])
        known = set(truth["affected_parents"])
        out[material] = {"found": sorted(found), "missed": sorted(known - found), "extra": sorted(found - known),
                         "completeness": len(found & known) / len(known)}
    return {"completeness": min(v["completeness"] for v in out.values()), "materials": out}


def inventory_reconciliation(data) -> dict:
    total = ok = 0
    for name, (shift, mult) in product(SCENARIOS, STRESS_GRID):
        r = simulate_from_data(load_scenario(name, data), lead_time_shift=shift, demand_multiplier=mult)
        for row in calculate_closing_stock(r):
            for rev in "bc":
                total += 1
                ok += row[f"rev_{rev}_reconciled"]
    return {"balances_checked": total, "reconciled": ok, "accuracy": ok / total if total else None,
            "runs": len(SCENARIOS) * len(STRESS_GRID)}


def shortage_excess_detection(data) -> dict:
    rows = []
    for name, exp in _expected()["scenarios"].items():
        r = simulate_from_data(load_scenario(name, data))
        got = {"total_shortage_units": r["total_shortage_units"],
               "first_shortage_week": r["shortage"]["first_shortage_week"],
               "shortage_week_list": r["shortage"]["shortage_week_list"],
               "rev_b_scrap_units": r["excess"]["rev_b_scrap_units"], "excess_value": r["excess_value"]}
        mismatches = {k: {"expected": exp[k], "got": v} for k, v in got.items() if exp[k] != v}
        if "expected_status" in exp and r["validation_status"] != exp["expected_status"]:
            mismatches["validation_status"] = {"expected": exp["expected_status"], "got": r["validation_status"]}
        rows.append({"scenario": name, "exact": not mismatches, "mismatches": mismatches})
    return {"scenarios": len(rows), "exact_matches": sum(r["exact"] for r in rows),
            "accuracy": sum(r["exact"] for r in rows) / len(rows), "detail": rows}


def audit_replay(data, repeats: int = 3) -> dict:
    runs = matches = 0
    for name in SCENARIOS:
        first = simulate_from_data(load_scenario(name, data))
        for _ in range(repeats):
            runs += 1
            matches += simulate_from_data(load_scenario(name, data)) == first
    return {"replays": runs, "identical": matches, "reproducibility": matches / runs}


def _norm(v):
    return " ".join(v.lower().split()) if isinstance(v, str) else v


def ecn_field_accuracy(predictions: dict[str, dict]) -> dict:
    """predictions: {"ECN-001": {field: value, ...}, ...} from an extractor.

    A field is correct when: PRESENT / INVALID -> the value matches (case and spacing ignored);
    MISSING / AMBIGUOUS / CONFLICT -> the extractor returned null (it abstained instead of guessing).
    Documents with no prediction count every field as wrong.
    """
    per_field, per_cat, correct, total, errors = {}, {}, 0, 0, []
    for path in sorted(EXPECTED.glob("ECN-*.json")):
        truth = json.loads(path.read_text(encoding="utf-8"))
        cid = truth["expected"]["change_id"]
        pred = predictions.get(cid) or {}
        for f, status in truth["field_status"].items():
            want = truth["expected"][f]
            hit = (cid in predictions) and (_norm(pred.get(f)) == _norm(want) if want is not None else pred.get(f) is None)
            correct += hit
            total += 1
            for bucket, key in ((per_field, f), (per_cat, truth["category"])):
                b = bucket.setdefault(key, [0, 0])
                b[0] += hit
                b[1] += 1
            if not hit:
                errors.append({"document": cid, "field": f, "status": status, "expected": want, "got": pred.get(f)})
    ratio = lambda d: {k: round(c / t, 4) for k, (c, t) in d.items()}   # noqa: E731
    return {"fields_scored": total, "correct": correct, "accuracy": correct / total,
            "by_field": ratio(per_field), "by_category": ratio(per_cat), "errors": errors}


def ranking_agreement(engine_order: list[str], reference_order: list[str]) -> dict:
    """Kendall tau over the items both lists rank (+1 identical order, -1 reversed) and top-3 overlap."""
    common = [x for x in reference_order if x in engine_order]
    pos_e = {x: engine_order.index(x) for x in common}
    pos_r = {x: reference_order.index(x) for x in common}
    pairs = list(combinations(common, 2))
    concordant = sum((pos_e[a] - pos_e[b]) * (pos_r[a] - pos_r[b]) > 0 for a, b in pairs)
    tau = (2 * concordant - len(pairs)) / len(pairs) if pairs else None
    return {"items_compared": len(common), "kendall_tau": tau,
            "top3_overlap": len(set(engine_order[:3]) & set(reference_order[:3])) / 3,
            "missing_from_engine": [x for x in reference_order if x not in engine_order]}


def severity_ranking_agreement(data) -> dict:
    """Compare the engine's order over all seeded-scenario exceptions with the manual reference list."""
    ref = json.loads((EXPECTED / "severity_reference.json").read_text(encoding="utf-8"))
    pool = []
    for name in SCENARIOS:
        for e in simulate_from_data(load_scenario(name, data))["exceptions"]:
            pool.append((e["severity_score"], f"{name}:{e['exception_id']}"))
    engine_order = [k for _, k in sorted(pool, key=lambda p: (-p[0], p[1]))]
    return {**ranking_agreement(engine_order, ref["ranking"]), "reference_status": ref["status"]}


def evaluate_all(data) -> dict:
    return {
        "bom_impact_completeness": bom_impact_completeness(data),
        "inventory_reconciliation": inventory_reconciliation(data),
        "shortage_excess_detection": shortage_excess_detection(data),
        "audit_replay": audit_replay(data),
        "severity_ranking_agreement": severity_ranking_agreement(data),
    }
