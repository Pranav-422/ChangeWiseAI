# Database migration report

Generated 2026-11-25T09:05:46+00:00 by `scripts/migration/verify_migration.py`.

* Target: PostgreSQL 17.12, hosted Supabase project (Mumbai).
* Result: **PASS**

| Source table | Target table | Source rows | Target rows | Missing | Values that differ |
|---|---|---:|---:|---:|---:|
| member1.materials | core.materials | 9 | 9 | 0 | 0 |
| member1.suppliers | core.suppliers | 5 | 5 | 0 | 0 |
| member1.engineering_changes | core.engineering_changes | 1 | 1 | 0 | 0 |
| member1.planning_groups | core.planning_groups | 6 | 6 | 0 | 0 |
| member1.bom | core.bom | 9 | 9 | 0 | 0 |
| member1.inventory | core.inventory | 5 | 5 | 0 | 0 |
| member1.demand | core.demand | 8 | 8 | 0 | 0 |
| member1.purchase_orders | core.purchase_orders | 5 | 5 | 0 | 0 |
| member1.simulation_runs | core.simulation_runs | 1 | 1 | 0 | 0 |
| member1.exceptions | core.exceptions | 1 | 1 | 0 | 0 |
| member3.ecn_reviews | app.ecn_reviews | 0 | 0 | 0 | 0 |
| member3.planning_runs | app.planning_runs | 0 | 0 | 0 | 0 |
| member3.what_if_requests | app.what_if_requests | 0 | 0 | 0 | 0 |
| member3.approvals | app.approvals | 0 | 0 | 0 | 0 |
| member3.action_items | app.action_items | 0 | 0 | 0 | 0 |
| member3.audit_log | app.audit_log | 0 | 0 | 0 | 0 |
| member1.candidate_plans | core.candidate_plans | 0 | 0 | 0 | 0 |
| member1.plan_actions | core.plan_actions | 0 | 0 | 0 | 0 |
| member1.audit_log | app.legacy_audit_events | 0 | 0 | 0 | 0 |

* Foreign keys: 32 defined, 0 not validated.
* Tables without Row Level Security: none.
* Audit chain: intact.
* Engine output on PostgreSQL data compared with the frozen baseline (every value of validation, BOM, simulation, exceptions, plans, ranking, robustness, baselines, replay):

  * base: identical
  * rev_c_supplier_delay: identical
  * excess_rev_b_orders: identical
  * blocked_supplier: identical
  * date_conflict: identical
  * missing_records: identical

## Decisions

* `plan_actions` (proposed by the engine) and `action_items` (approved tasks) stay separate; `action_items.plan_action_id` links them, and `action_status_history` records every status.
* `app.audit_log` is the one live audit log. Member 1's audit rows go to `app.legacy_audit_events` with their original IDs. `app.audit_events` shows both.
* Member 1's proposed `action_tracker` is superseded by `action_items`; it is not created. Its rows, if any, are reported as rejected by the import.
* Snapshots that are hashed or replayed use JSON, because JSONB would rewrite them. Other JSON uses JSONB.
* Money is NUMERIC; flags are BOOLEAN; IDs are unchanged. The engines still receive floats and 0/1 flags.
* `audit_log.created_at` stays TEXT because it is inside the hash. `recorded_at` is the server's own time.
* The SQLite files are not modified. Backups are read-only copies with SHA-256 sums in `backups/` (not committed).
