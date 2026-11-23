"""Evaluation metrics. Member 2 measures its own; the others are consumed as evidence, never invented.

External evidence is a dict {metric_key: {"value": ..., "evidence": "..."}} supplied by the owner's
test run. Without it the metric is reported as PENDING.
"""

EXTERNAL_METRICS = {
    "bom_impact_completeness": "Member 1",
    "shortage_detection_accuracy": "Member 1",
    "severity_ranking_agreement": "Member 1",
    "ecn_field_extraction_accuracy": "Member 3",
    "what_if_mapping_accuracy": "Member 3",
    "llm_claim_verification_rate": "Member 3",
}


def ratio(passed, total):
    return {"passed": passed, "total": total, "value": passed / total if total else None}


def inventory_reconciliation(weekly_tables):
    """opening + receipts - usage = closing, each opening = previous closing, stock never negative."""
    passed = total = 0
    for weekly in weekly_tables:
        for rev in ("rev_b", "rev_c"):
            previous = None
            for row in weekly:
                opening, closing = row[f"{rev}_opening"], row[f"{rev}_closing"]
                total += 1
                passed += (opening + row[f"{rev}_receipts"] - row[f"{rev}_usage"] == closing
                           and closing >= 0 and previous in (None, opening))
                previous = closing
    return ratio(passed, total)


def hard_rule_violations(results):
    """Rejection reasons attached to any recommended plan. Must be zero."""
    return sum(p["feasibility"] != "FEASIBLE" for r in results for p in r["recommendations"])


def escalation_routing(results, expected):
    """A scenario counts only when the exact set of escalation codes matches."""
    rows = [{"scenario_id": r["scenario_id"], "expected": sorted(expected[r["scenario_id"]]),
             "actual": sorted(e["code"] for e in r["escalations"])} for r in results]
    for row in rows:
        row["correct"] = row["expected"] == row["actual"]
    return {**ratio(sum(r["correct"] for r in rows), len(rows)), "rows": rows}


def replay_reproducibility(flags):
    return ratio(sum(flags), len(flags))


def solver_agreement(rows):
    """Only backends that actually ran count, per backend."""
    return {name: ratio(sum(r["agrees"] for r in ran), len(ran))
            for name in sorted({r["backend"] for r in rows})
            for ran in [[r for r in rows if r["backend"] == name and r["status"] == "RUN"]]}


def external_metrics(evidence=None):
    evidence = evidence or {}
    return [
        {"metric": key, "owner": owner,
         "status": "REPORTED" if key in evidence else "PENDING",
         "value": evidence.get(key, {}).get("value"),
         "evidence": evidence.get(key, {}).get("evidence")}
        for key, owner in EXTERNAL_METRICS.items()
    ]
