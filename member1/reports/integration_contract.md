# Member 1 ↔ Members 2 & 3 integration contract

Status: **PROPOSED, engine v`m1-1.1.0`**. Items marked ⚠ need team sign-off. Once agreed, change them only by bumping `engine_version` in `config/settings.yaml`.

## 1. The simulator call (Member 2 calls this for every candidate plan and stress run)

```python
from engine.inventory import simulate_inventory

result = simulate_inventory(
    materials, inventory, demand, purchase_orders,   # DataFrames or lists of dicts (never mutated)
    engineering_change,                              # dict, one engineering_changes row
    suppliers,                                       # ALWAYS pass it: enables lead-time + supplier-status rules
    lead_time_shift=0,          # robustness: delays every Rev C receipt by N weeks (0, 1, 2)
    demand_multiplier=1.0,      # robustness: 0.9 / 1.0 / 1.1 (rounded half-up per week)
    average_weekly_demand=None, # D for 4-week cover; pass a fixed value to hold D equal across plans ⚠
    scenario_id="P1-S5",        # free label, stored with the run
)
```

`simulate_from_data(data, change_id, **kwargs)` does the same from the dict returned by `load_csv_data()` or `load_data_from_db()`. It raises `KeyError` for an unknown change.

* `plant_id` defaults to `settings.yaml` (PUMP-PLANT-01). Rows for other plants are ignored.
* `horizon_weeks` must be ≥ 1, otherwise `ValueError`.
* Speed: about 4 ms per run. For thousands of runs, convert the tables to lists of dicts once with `engine.data_loader.to_records` and pass those lists.

Evaluation evidence for Member 2's report: `engine.metrics.evaluate_all(data)`, or `python scripts/evaluate_member1.py`, which writes `reports/member1_metrics.json`. Member 3's extractor accuracy: `engine.metrics.ecn_field_accuracy({change_id: {field: value}})`.

### How Member 2 expresses each action (edit a copy of the inputs, then call the simulator)

| Action | Input change |
|---|---|
| Shift effective week | `engineering_change["effective_week"] = w` |
| Reduce Rev B PO | `quantity -= n` (keep ≥ 0 and `n ≤ max_reduction_quantity`) |
| Cancel Rev B PO | `po_status = "Cancelled"` |
| Defer Rev B / Rev C PO | `arrival_week += n` (`n ≤ maximum_defer_weeks`) |
| Expedite Rev C PO | `arrival_week = order_week + supplier.expedited_lead_time_weeks`, `expedited = 1` |
| Alternate supplier | add a PO row with that `supplier_id`, a `purchasing_group` and an `order_week` |

Fees for the action cost C (`cancellation_fee`, `reduction_fee`, `expedite_fee`) are columns on `purchase_orders`. Member 1 does not compute C.

## 2. Allocation policy (identical in every plan)

1. Receipts arrive at the **start** of their week.
2. `available = on_hand − reserved`. Reserved stock (50 Rev B units, held for KIT-301 service orders) is never used for production and is never counted as scrap.
3. **Safety stock is a protected floor**: production uses `max(0, available − safety_stock)`. Demand beyond that is shortage. ⚠
4. Week t, effective week E, use-up end U:
   * t < E and t ≤ U → Rev B only
   * t ≥ E → Rev C first; if interchangeable and t ≤ U, Rev B covers what Rev C cannot
   * t < E and t > U → no permitted revision, so all demand is unmet (`SIM_NO_PERMITTED_REVISION`)
   * Rev B is **never** used after U. Rev C replaces Rev B one-for-one.
5. Lead time: arrival ≥ `order_week + lead_time` (the expedited lead time when `expedited = 1` and the supplier offers it). An earlier arrival is moved to the earliest feasible week and flagged `SIM_LEAD_TIME_VIOLATION`. Member 2's hard rule 3 should reject such plans.
6. Receipts from **Blocked / Unqualified** suppliers are excluded from supply (`SIM_RESTRICTED_SUPPLIER_RECEIPT_EXCLUDED`).
7. `closing = opening + receipts − usage ≥ 0` and `next opening = closing`. Unmet demand is recorded once per week (`demand = rev_b_usage + rev_c_usage + shortage`).

## 3. Shortage and excess definitions

* **S** = Σ weekly `shortage` → `result["total_shortage_units"]`
* **E_B** = `rev_b_scrap_units × unit_cost_B`, where `rev_b_scrap_units` = free Rev B at the end of week U **plus Rev B receipts arriving after U**. A Rev B PO deferred past the use-up end therefore still counts as scrap and cannot hide it.
* **E_C** = `max(0, rev_c_closing − 4 × D) × unit_cost_C`, with Rev C measured at the horizon end (W8).
* **D** defaults to the mean weekly demand over W1–W8 (121.25 in the base case, so 4D = 485). ⚠ The alternative is post-changeover demand only (150/week).
* `result["excess_value"]` = E_B + E_C. Former safety stock inside the scrap figure is shown in `rev_b_scrap_from_safety_stock`.

## 4. Result structure (stable keys)

```text
simulation_id         "SIM-" + first 12 hex chars of input_snapshot_hash. Same inputs give the same id (audit replay)
input_snapshot_hash   sha256 of inputs + change + parameters + engine_version (row order ignored)
validation_status     VALID | NEEDS_REVIEW | INSUFFICIENT_DATA | INVALID
weeks[]               week, demand, applicable_revision (B/C/None), shortage,
                      rev_{b,c}_{opening, receipts, reserved, available, safety_stock, usable, usage, closing, unmet}
shortage              total_shortage_units, first_shortage_week, shortage_weeks, shortage_week_list,
                      weekly_unmet_demand[], affected_materials[], estimated_financial_impact
excess                rev_b_scrap_units, rev_b_scrap_value, rev_c_closing_units, average_weekly_demand,
                      rev_c_excess_value, total_excess_value, plus the breakdown fields
total_shortage_units, excess_value      shortcuts for ranking
exceptions[]          severity-ranked (section 6)
issues[]              {code, status, severity, record, description, resolution, week}
receipts[]            the receipts actually simulated (after lead-time correction)
```

If `validation_status` is INVALID or INSUFFICIENT_DATA because of the engineering change itself, `weeks` is `[]` and the numeric fields are `None`. Member 2 must not rank such a plan (hard rule 7).

## 5. Validation (`engine.validation.validate_all_inputs(data, change_id)`)

Returns `{status, ready_for_simulation, results{scope: …}, issues[]}`. Member 3's ECN adapter should call `validate_engineering_change(extracted_change, materials)` rather than re-implementing it. A blocked supplier on an **unrelated** material is INFO only. On an **affected** PO it is NEEDS_REVIEW: sourcing actions on that PO are invalid, but the change itself is still plannable.

## 6. Exceptions (table 11, `exceptions`)

`exception_id` (stable, e.g. `EXC-PRODUCTION_SHORTAGE-MAT-102-W6`), `exception_type`, `material_id`, `week`, `quantity`, `financial_impact`, `severity_score` 0–100, `severity_level` CRITICAL/HIGH/MEDIUM/LOW, `severity_rank`, `owner_role`, `description`, `recommended_action`, `status`.

Score = 100 × (0.5·type_weight + 0.3·min(1, impact/₹1,00,000) + 0.2·urgency), where urgency = (H − week + 1)/H. Data problems that block planning (DATA_INVALID, DATA_INSUFFICIENT) never score below 80, so they are always CRITICAL. Weights are in `settings.yaml`. ⚠ Severity agreement: `documents/expected_outputs/severity_reference.json` is a DRAFT ranking. A teammate acting as planner must re-rank it by hand before the metric is quoted.

Validation codes added in v1.1.0: weeks outside 1–52 are INVALID; `PO_CREATED_AFTER_APPROVAL` (a Rev B PO placed at or after `approval_week`, the purchasing block) is NEEDS_REVIEW.

## 7. Tables 9–13 (`database/schema.sql`)

`candidate_plans` (key `optimization_run_id + plan_id`), `plan_actions` (8 action types), `exceptions`, `action_tracker`, and `audit_log`. The audit log is append-only: UPDATE and DELETE are rejected by triggers, and rows carry `previous_hash` / `event_hash` for a tamper-evident chain. ⚠ Members 2 and 3 should review the columns before writing to these tables.

## 8. Open decisions for the team ⚠

1. Safety stock: protected floor (current) or usable with a warning?
2. D for E_C: horizon mean (current) or post-changeover mean?
3. Near-tie percentage denominator (Member 2): the smaller or the larger E + C?
4. ECN field name: the Member 1 spec says `use_up_end`, but the table and Member 3 use `use_up_end_week`. `use_up_end_week` is used everywhere here.
5. The deck's worked example (slide 6) uses ₹400 for Rev C. The data uses ₹450 per the Member 1 spec. Regenerate slide 6 from real Member 2 output.
