import json

import pytest

from engine import ROOT
from engine.metrics import (audit_replay, bom_impact_completeness, ecn_field_accuracy, inventory_reconciliation,
                            ranking_agreement, severity_ranking_agreement, shortage_excess_detection)

TRUTH = {p.stem: json.loads(p.read_text(encoding="utf-8"))
         for p in (ROOT / "documents" / "expected_outputs").glob("ECN-*.json")}


def test_slide8_targets_met(data):
    assert bom_impact_completeness(data)["completeness"] == 1.0
    rec = inventory_reconciliation(data)
    assert rec["accuracy"] == 1.0 and rec["runs"] == 54
    det = shortage_excess_detection(data)
    assert det["accuracy"] == 1.0, det["detail"]
    assert audit_replay(data, repeats=1)["reproducibility"] == 1.0


def test_perfect_extractor_scores_100():
    preds = {cid: t["expected"] for cid, t in TRUTH.items()}
    r = ecn_field_accuracy(preds)
    assert r["fields_scored"] == 180 and r["accuracy"] == 1.0 and r["errors"] == []


def test_extractor_that_guesses_missing_values_is_penalised():
    preds = {cid: dict(t["expected"]) for cid, t in TRUTH.items()}
    preds["ECN-006"]["effective_week"] = 6          # invented, the document never states it
    preds["ECN-017"]["old_revision"] = "Rev B"      # silently picked one side of a conflict
    r = ecn_field_accuracy(preds)
    assert r["correct"] == 178 and {e["status"] for e in r["errors"]} == {"MISSING", "CONFLICT"}


def test_matching_ignores_case_and_spacing_and_missing_documents_score_zero():
    preds = {cid: t["expected"] for cid, t in TRUTH.items() if cid != "ECN-018"}
    preds["ECN-001"] = {**preds["ECN-001"], "reason": "  improved   MECHANICAL durability "}
    r = ecn_field_accuracy(preds)
    assert r["correct"] == 170 and all(e["document"] == "ECN-018" for e in r["errors"])


@pytest.mark.parametrize("engine,tau", [(["a", "b", "c"], 1.0), (["c", "b", "a"], -1.0)])
def test_ranking_agreement(engine, tau):
    assert ranking_agreement(engine, ["a", "b", "c"])["kendall_tau"] == tau


def test_severity_reference_covers_every_engine_exception(data):
    r = severity_ranking_agreement(data)
    assert r["missing_from_engine"] == [] and r["items_compared"] == 19 and r["kendall_tau"] > 0.5
