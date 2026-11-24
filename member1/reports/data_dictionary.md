# Data dictionary: synthetic SAP-like inputs

All data is synthetic. Plant `PUMP-PLANT-01`. Weeks are integers (W1 = 1; values ≤ 0 mean before the horizon). Money is INR. Quantities are whole units (EA). The source of truth is `data/generate_synthetic.py`, which writes `data/synthetic/*.csv`.

## materials (9 rows)
| Column | Type | Meaning |
|---|---|---|
| material_id | text, PK | Unique material number (PUMP-, SUB-, KIT-, MAT-) |
| material_name | text | Name. Bracket names include the revision, e.g. "Mounting Bracket Rev B" |
| description | text | Free text |
| revision | `Rev X` | Revision of this material record |
| material_type | FINISHED / ASSEMBLY / COMPONENT / KIT | Used to find finished products in the BOM report |
| material_status | Active / Released / Phase-Out / Obsolete / Blocked | MAT-101 is Phase-Out, MAT-102 is Released |
| unit_cost | ₹ ≥ 0 | Rev B ₹400, Rev C ₹450 |
| unit_of_measure | text | EA |

## bom (9 rows): parent uses child
| Column | Meaning |
|---|---|
| bom_id | PK |
| parent_material_id / child_material_id | FKs to materials |
| quantity_per_parent | > 0 (e.g. 4 bolts per sub-assembly) |
| effective_from / effective_to | Week range of the BOM line. SUB-201 → MAT-101 runs W1–W5, SUB-201 → MAT-102 runs from W6 |

Where-used for MAT-101: SUB-201 → PUMP-001, SUB-201 → PUMP-002, and KIT-301 (service kit).

## inventory (5 rows)
| Column | Meaning |
|---|---|
| inventory_id | PK |
| material_id, plant_id | Which stock |
| on_hand | Physical stock ≥ 0 |
| reserved | Committed to other demand (Rev B: 50 for KIT-301 service orders); ≤ on_hand |
| safety_stock | Protected floor (Rev B 30, Rev C 20) |
| inventory_date | Snapshot date (2026-11-23 = start of W1) |

`available = on_hand − reserved` is computed, never stored.

## demand (8 rows)
| Column | Meaning |
|---|---|
| demand_id | PK |
| product_id | Finished product (PUMP-001) |
| material_id | Bracket requirement as MRP recorded it (MAT-101 for W1–W5, MAT-102 for W6–W8). The simulator pools both and assigns the revision by the changeover rules |
| week, required_quantity | 80, 100, 100, 120, 120, 150, 150, 150 brackets |

## purchase_orders (5 rows)
| Column | Meaning |
|---|---|
| po_id | PK |
| material_id, supplier_id | FKs |
| quantity | Units ≥ 0 |
| order_week | Week the PO was placed. Used for the lead-time check (added column) |
| arrival_week | Scheduled arrival, ≥ 1 |
| purchasing_group | Buying group (see planning_groups) |
| po_status | Open / Confirmed (both receivable), Cancelled, Received |
| cancel_allowed_until | Last week a cancellation is allowed |
| maximum_defer_weeks | Max weeks the arrival may be pushed out |
| max_reduction_quantity | Max units the quantity may be reduced by (added column) |
| cancellation_fee / reduction_fee / expedite_fee | ₹ per action, ≥ 0 |
| expedited | 1 when the PO uses the supplier's expedited lead time (added column) |

| PO | Material | Supplier | Qty | Order → Arrival | Notes |
|---|---|---|---|---|---|
| PO-001 | MAT-101 Rev B | S1 | 200 | W-2 → W3 | cancel ≤ W1, defer ≤ 2 |
| PO-002 | MAT-101 Rev B | S1 | 100 | W0 → W5 | cancel ≤ W3, defer ≤ 1 |
| PO-003 | MAT-102 Rev C | S2 | 500 | W2 → W6 | lead 4; expedite to W5 for ₹12,000 |
| PO-004 | MAT-202 | S5 | 120 | → W2 | unrelated to the change |
| PO-005 | MAT-203 | S3 (Blocked) | 2000 | → W4 | unrelated; shows a blocked supplier does not block the change |

## suppliers (5 rows)
| Column | Meaning |
|---|---|
| supplier_id | PK |
| supplier_status | Approved / Blocked / Unqualified |
| lead_time_weeks | Normal lead time (nullable = unknown, which is flagged) |
| expedite_available, expedited_lead_time_weeks, expedite_fee | Expedite offer |
| restriction_note | Required reason for Blocked / Unqualified |

S1 Approved (Rev B, lead 3) · **S2 Approved (Rev C, lead 4, expedite 3)** · S3 Blocked (quality notification QN-4471) · S4 Unqualified (Rev C PPAP not approved) · S5 Approved (impellers).

## planning_groups (6 rows): who may buy what from whom
Key `(group_id, material_id, supplier_id)`. `authorization_status` is Authorized or Unauthorized. PG-10 may buy Rev B from S1 and Rev C from S2. It is unauthorized for Rev C from S3. PG-20 is unauthorized for Rev C from S4.

## engineering_changes (1 row)
| Column | Value for ECN-001 |
|---|---|
| change_id | ECN-001 |
| part_number → new_material_id | MAT-101 → MAT-102 (`new_material_id` is an added column) |
| old_revision → new_revision | Rev B → Rev C |
| effective_week / use_up_end_week | 6 / 5 |
| interchangeability | 1 (true) |
| reason / approver | Improved mechanical durability / Engineering Manager |
| approval_status / approval_week | Approved / 1 (purchasing block for new Rev B POs starts here; added column) |
| created_at | 2026-11-20T09:00:00 |

## Seeded scenario variants (`engine/scenarios.py`)
`base`, `rev_c_supplier_delay` (PO-003 at W8), `excess_rev_b_orders` (PO-002 = 400), `blocked_supplier` (S2 Blocked), `date_conflict` (use-up W3), `missing_records` (no Rev C stock row, S2 lead time null).
