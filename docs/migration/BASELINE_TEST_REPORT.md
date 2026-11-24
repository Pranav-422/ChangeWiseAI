# Baseline test report (before any migration change)

Date: 24 November 2026. Commit `d562da2`. Windows 11, Python 3.12.10, the repository's existing environment
(`member2/.venv`: pandas 3.1.1, numpy 2.5.5, ortools 9.15.6755, PuLP 2.9.0, pydantic 2.14.4, pypdf 7.1.1, streamlit 1.67.0, pytest 9.2.0).

| Suite | Command | Passed | Failed | Skipped |
|---|---|---:|---:|---:|
| Member 1 | `cd member1 && python -m pytest -q` | 120 | 3 | 0 |
| Member 2 | `python -m pytest member2 -q` | 232 | 0 | 0 |
| Member 3 | `python -m pytest member3 -q` | 319 | 0 | 0 |

The three failures are the same cause: Windows Application Control blocks PyMuPDF's native library on this computer.

* `tests/test_dashboards.py::test_dashboard_renders[ecn_intake.py]`
* `tests/test_data_generation.py::test_ecn_pdfs_are_extractable_with_pymupdf`
* `tests/test_data_generation.py::test_ecn_pdfs_regenerate_byte_identical`

## Numerical baseline

`python -m scripts.migration.capture_baseline` ran the real Member 1 and Member 2 code on all six scenarios and wrote
`docs/migration/baseline/*.json` with SHA-256 sums. Each file holds validation, BOM impact, weekly simulation, shortage, excess,
exceptions, the Member 2 dataset, every feasible and rejected plan, ranking, near-ties, robustness, baselines A and B, the replay verdict
and the template explanation with its verification.

| Scenario | Validation | Unmet, no action | Excess, no action | Decision | Feasible / rejected | Leading plan | S | E + C | Robust |
|---|---|---:|---:|---|---|---|---:|---:|---|
| base | VALID | 0 | 92,000 | ESCALATED (near-tie) | 1344 / 7 | Reduce PO-001 by 200 | 0 | 17,000 | 2/9 |
| rev_c_supplier_delay | VALID | 300 | 92,000 | ESCALATED (near-tie) | 1680 / 6 | Expedite PO-003 by 2 wk; Reduce PO-001 by 200 | 0 | 29,000 | 2/9 |
| excess_rev_b_orders | VALID | 0 | 212,000 | RECOMMENDED | 1344 / 7 | Cancel PO-002; Reduce PO-001 by 100 | 0 | 21,000 | 2/9 |
| blocked_supplier | NEEDS_REVIEW | 450 | 92,000 | NO_FEASIBLE_PLAN | 0 / 7 | none | - | - | - |
| date_conflict | NEEDS_REVIEW | 240 | 188,000 | INVALID_DATA | 0 / 0 | none | - | - | - |
| missing_records | INSUFFICIENT_DATA | 0 | 92,000 | INVALID_DATA | 0 / 0 | none | - | - | - |

Amounts in rupees, from synthetic data. The base row matches Member 1's report: shortage 0, 230 units of Rev B scrap, Rs 92,000.
