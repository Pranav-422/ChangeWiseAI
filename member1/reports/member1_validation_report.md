# Member 1 validation report

Engine `m1-1.1.0` · run 2026-11-24 · Python 3.13 (code is 3.11-compatible) · synthetic data only.
Reproduce with `python scripts/run_pipeline.py`, `python scripts/evaluate_member1.py` and `python -m pytest`.

## 0. Slide-8 metrics owned by Member 1 (`scripts/evaluate_member1.py` → `reports/member1_metrics.json`)

| Measure | Target | Result |
|---|---|---|
| BOM impact completeness (vs hand-checked set) | 100% | **100%** (4 of 4 affected parents) |
| Inventory reconciliation (6 scenarios × 9 stress runs) | Exact | **864 / 864** week-revision balances |
| Shortage & excess detection (week, qty, scrap vs hand-checked) | Exact week | **6 / 6** scenarios exact |
| Audit replay (re-run gives same id and result) | 100% | **18 / 18** |
| Severity ranking agreement (Kendall tau vs reference) | Reported | **0.72**. The reference list is a DRAFT; a teammate must re-rank it by hand |
| Simulator speed | — | **≈ 3.9 ms per run** (about 12 s for 3,000 optimiser runs) |

Hand-checked expectations, with working, are in `documents/expected_outputs/simulation_expected.json`. `engine.metrics.ecn_field_accuracy(predictions)` scores Member 3's extractor over the 180 ECN fields. A guessed value for a missing, ambiguous or conflicting field counts as wrong.

## 1. Test suite

**123 tests, 123 passed.**

| File | Tests | Covers |
|---|---|---|
| test_inventory.py | 39 | Base case hand-check, the 14 required edge cases, lead time, expedite, blocked supplier, interchangeability, scrap guard, determinism, input immutability, plant filter, bad horizon |
| test_validation.py | 29 | Every validation rule, unrelated-vs-affected supplier handling, weeks beyond 52, Rev B PO after approval |
| test_database.py | 12 | 14 tables, repeatable init, FK/CHECK/UNIQUE enforcement, atomic load, append-only audit log, replay |
| test_bom_impact.py | 8 | Direct/indirect parents, multi-level, multiple parents, cycles, missing material, quantity roll-up |
| test_severity.py | 8 | Score formula, bands, urgency, shortage outranks scrap, blocking data is CRITICAL, deterministic ties |
| test_metrics.py | 7 | Slide-8 targets, ECN accuracy scorer (perfect, guessing penalised, missing docs), ranking agreement |
| test_data_generation.py | 6 | Reproducible CSVs and byte-identical PDFs, referential integrity, base values, ECN distribution, PyMuPDF extraction |
| test_excess.py | 5 | Spec worked example (₹85,000), cover rule, negative inputs, fixed D |
| test_dashboards.py | 5 | All three Streamlit views render headless; lead-time slider updates the KPI; change after W8 |
| test_shortage.py | 4 | Spec worked example (S = 30, first W3, 2 weeks), no double counting |

Mutation check: making safety stock usable in `engine/inventory.py` makes 4 tests fail, so the suite detects a real policy regression.

A code review (high recall) found 8 issues. All are fixed, with regression tests: weeks above 52 accepted, opaque error for an unknown change, plants mixed by default, `horizon_weeks=0` silently replaced, blocking data ranked below scrap, raw IntegrityError on save, dashboard crash for a change after W8, and Rev B POs after approval not flagged.

## 2. Base scenario (ECN-001, Rev B → Rev C, effective W6, use-up W5) — status VALID

| Week | Demand | Rev B open | +Rcpt | −Use | Close | Rev C open | +Rcpt | −Use | Close | Short |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 80 | 500 | 0 | 80 | 420 | 0 | 0 | 0 | 0 | 0 |
| 2 | 100 | 420 | 0 | 100 | 320 | 0 | 0 | 0 | 0 | 0 |
| 3 | 100 | 320 | 200 | 100 | 420 | 0 | 0 | 0 | 0 | 0 |
| 4 | 120 | 420 | 0 | 120 | 300 | 0 | 0 | 0 | 0 | 0 |
| 5 | 120 | 300 | 100 | 120 | 280 | 0 | 0 | 0 | 0 | 0 |
| 6 | 150 | 280 | 0 | 0 | 280 | 0 | 500 | 150 | 350 | 0 |
| 7 | 150 | 280 | 0 | 0 | 280 | 350 | 0 | 150 | 200 | 0 |
| 8 | 150 | 280 | 0 | 0 | 280 | 200 | 0 | 150 | 50 | 0 |

* Inventory reconciliation: **all 16 week-revision balances reconcile** (opening + receipts − usage = closing, never negative).
* S = **0**.
* Rev B scrap = 280 − 50 reserved = **230 units** (30 of them former safety stock), so E_B = 230 × ₹400 = **₹92,000**.
* Rev C closing 50 is below 4D = 4 × 121.25 = 485, so E_C = **₹0**. E = **₹92,000**.
* Exceptions: 1. `EXC-REV_B_SCRAP_RISK-MAT-101-W5`, score 67.6, HIGH, owner Materials Management.
* BOM impact: **IDENTIFIED**, 3 paths, top-level products KIT-301, PUMP-001, PUMP-002.
* Input validation: **VALID**. Blocked S3 on unrelated PO-005 is reported as INFO only.

This is the "do nothing" case (Baseline A): no shortage, ₹92,000 of Rev B write-off. That is what Member 2 must beat.

## 3. Seeded scenarios

| Scenario | Status | S | E (₹) | Top exception |
|---|---|---|---|---|
| base | VALID | 0 | 92,000 | Rev B scrap risk W5 |
| rev_c_supplier_delay (PO-003 → W8) | VALID | 300 | 92,000 | Production shortage W6 (CRITICAL) |
| excess_rev_b_orders (PO-002 = 400) | VALID | 0 | 212,000 | Rev B scrap risk W5 |
| blocked_supplier (S2 Blocked) | NEEDS_REVIEW | 450 | 92,000 | Production shortage W6 |
| date_conflict (use-up W3) | NEEDS_REVIEW | 240 | 188,000 | Production shortage W4 (revision gap) |
| missing_records | INSUFFICIENT_DATA | 0 | 92,000 | Missing Rev C stock record (CRITICAL). Not plannable until data is supplied |

## 4. ECN test collection

18 PDFs: 5 complete, 4 missing fields, 4 ambiguous, 3 incorrect dates, 2 conflicting revisions. With 10 fields each, that is 180 scorable fields. Every stated value, ambiguous phrase and conflicting value was confirmed extractable with PyMuPDF. Ground truth is in `documents/expected_outputs/`; per-field status is in `documents/manifest.json`.

## 5. Known limits

* One plant, one engineering change, 8-week horizon, weekly buckets.
* Demand is given already exploded to brackets. Sub-assembly WIP containing Rev B is not modelled.
* Severity weights are a documented heuristic, not calibrated against real planner rankings.
* Tables 9, 10, 12 and 13 have no Member 1 logic. They are schema only, pending Member 2 and 3 sign-off.
