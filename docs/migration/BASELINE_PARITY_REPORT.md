# Baseline parity report

Question: does the cloud path give the same numbers as the code that was frozen before the migration?
Answer: yes. No value differs in any of the six scenarios.

## Method

`docs/migration/baseline/*.json` was written by the original code before any change and is protected by SHA-256 sums.

1. **Data level** (`scripts/migration/capture_baseline.py --check backend.app.integrations.member1_postgres`, also a test): the same capture
   runs on PostgreSQL tables. Every leaf of every structure is compared: validation, BOM impact, weekly simulation, shortage, excess,
   exceptions with severity, Member 2 dataset, candidate plans, rejected plans with reasons, ranking, near-ties, robustness runs,
   baselines A and B, replay verdict, template explanation and its verification. The only value set aside is `computation_seconds`.
2. **API level** (`backend/tests/test_database.py::test_api_results_equal_the_frozen_baseline`): base, supplier delay, excess orders,
   blocked supplier and missing records run through HTTP, JSON storage and paging, and are compared with the same files: all 1344 to 1680 ranked plans with
   their order and cost, rejections, escalations, hashes, the nine stress runs of each recommended plan, and the weekly rows.
3. **Migration level** (`verify_migration`): every value of every migrated row.

## Result

| Scenario | PostgreSQL data | Through the API |
|---|---|---|
| base | identical | identical |
| rev_c_supplier_delay | identical | identical |
| excess_rev_b_orders | identical | identical |
| blocked_supplier | identical | identical |
| date_conflict | identical | stops earlier: the ECN contradicts the changed record and cannot be confirmed |
| missing_records | identical | identical (INVALID_DATA, no plan) |

Simulation IDs and input hashes are identical too, so stored and new runs can be compared directly.

## Precision

* Money is stored as NUMERIC and read as a float, the type the engines always used. The amounts have at most two decimals, so no value changes.
* Flags are stored as BOOLEAN and given to Member 1 as 0/1.
* Dates are stored as DATE and TIMESTAMP and read in the same ISO text.
* Tables pass through CSV text once on reading, so column types are exactly those of `load_csv_data()`.
