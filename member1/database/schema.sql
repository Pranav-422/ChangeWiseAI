-- ChangeWise AI - shared SQLite schema (14 tables). Owner: Member 1.
-- Tables 9-13 are the PROPOSED integration contract with Members 2 and 3 (see reports/integration_contract.md).
-- Weeks are integers: W1 = 1. Money is INR. Quantities are units (EA).
PRAGMA foreign_keys = ON;

-- 2. Material master
CREATE TABLE materials (
    material_id      TEXT PRIMARY KEY,
    material_name    TEXT NOT NULL,
    description      TEXT,
    revision         TEXT NOT NULL CHECK (revision GLOB 'Rev [A-Z]'),
    material_type    TEXT NOT NULL CHECK (material_type IN ('FINISHED','ASSEMBLY','COMPONENT','KIT')),
    material_status  TEXT NOT NULL CHECK (material_status IN ('Active','Released','Phase-Out','Obsolete','Blocked')),
    unit_cost        REAL NOT NULL CHECK (unit_cost >= 0),
    unit_of_measure  TEXT NOT NULL DEFAULT 'EA'
);

-- 1. Engineering changes (one row per ECN)
CREATE TABLE engineering_changes (
    change_id          TEXT PRIMARY KEY,
    part_number        TEXT NOT NULL REFERENCES materials(material_id),   -- old revision material
    new_material_id    TEXT NOT NULL REFERENCES materials(material_id),   -- new revision material
    old_revision       TEXT NOT NULL,
    new_revision       TEXT NOT NULL,
    effective_week     INTEGER NOT NULL CHECK (effective_week >= 1),
    use_up_end_week    INTEGER NOT NULL CHECK (use_up_end_week >= 1),
    interchangeability INTEGER NOT NULL CHECK (interchangeability IN (0,1)),
    reason             TEXT,
    approver           TEXT,
    approval_status    TEXT NOT NULL CHECK (approval_status IN ('Draft','Pending','Approved','Rejected')),
    approval_week      INTEGER,          -- purchasing block for the old revision starts here
    created_at         TEXT NOT NULL,
    CHECK (part_number <> new_material_id),
    CHECK (old_revision <> new_revision)
);

-- 3. Bill of materials (parent uses child)
CREATE TABLE bom (
    bom_id              TEXT PRIMARY KEY,
    parent_material_id  TEXT NOT NULL REFERENCES materials(material_id),
    child_material_id   TEXT NOT NULL REFERENCES materials(material_id),
    quantity_per_parent REAL NOT NULL CHECK (quantity_per_parent > 0),
    effective_from      INTEGER NOT NULL CHECK (effective_from >= 1),
    effective_to        INTEGER CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (parent_material_id <> child_material_id),
    UNIQUE (parent_material_id, child_material_id, effective_from)
);
CREATE INDEX idx_bom_child ON bom(child_material_id);     -- where-used lookups
CREATE INDEX idx_bom_parent ON bom(parent_material_id);

-- 4. Inventory snapshot. available_stock = on_hand - reserved (computed, never stored)
CREATE TABLE inventory (
    inventory_id   TEXT PRIMARY KEY,
    material_id    TEXT NOT NULL REFERENCES materials(material_id),
    plant_id       TEXT NOT NULL,
    on_hand        INTEGER NOT NULL CHECK (on_hand >= 0),
    reserved       INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0 AND reserved <= on_hand),
    safety_stock   INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
    inventory_date TEXT NOT NULL,
    UNIQUE (material_id, plant_id, inventory_date)
);
CREATE INDEX idx_inventory_material ON inventory(material_id);

-- 5. Weekly demand (component requirement already exploded from the product)
CREATE TABLE demand (
    demand_id         TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES materials(material_id),
    material_id       TEXT NOT NULL REFERENCES materials(material_id),
    plant_id          TEXT NOT NULL,
    week              INTEGER NOT NULL CHECK (week >= 1),
    required_quantity INTEGER NOT NULL CHECK (required_quantity >= 0),
    UNIQUE (product_id, material_id, plant_id, week)
);
CREATE INDEX idx_demand_material_week ON demand(material_id, week);

-- 7. Suppliers
CREATE TABLE suppliers (
    supplier_id               TEXT PRIMARY KEY,
    supplier_name             TEXT NOT NULL,
    supplier_status           TEXT NOT NULL CHECK (supplier_status IN ('Approved','Blocked','Unqualified')),
    lead_time_weeks           INTEGER CHECK (lead_time_weeks IS NULL OR lead_time_weeks >= 0),
    expedite_available        INTEGER NOT NULL DEFAULT 0 CHECK (expedite_available IN (0,1)),
    expedited_lead_time_weeks INTEGER CHECK (expedited_lead_time_weeks IS NULL OR expedited_lead_time_weeks >= 0),
    expedite_fee              REAL NOT NULL DEFAULT 0 CHECK (expedite_fee >= 0),
    restriction_note          TEXT      -- mandatory reason when status is Blocked/Unqualified (checked in validation)
);

-- 8. Purchasing groups: which group may buy which material from which supplier
CREATE TABLE planning_groups (
    group_id             TEXT NOT NULL,
    group_name           TEXT NOT NULL,
    material_id          TEXT NOT NULL REFERENCES materials(material_id),
    supplier_id          TEXT NOT NULL REFERENCES suppliers(supplier_id),
    authorization_status TEXT NOT NULL CHECK (authorization_status IN ('Authorized','Unauthorized')),
    PRIMARY KEY (group_id, material_id, supplier_id)
);

-- 6. Purchase orders
CREATE TABLE purchase_orders (
    po_id                  TEXT PRIMARY KEY,
    material_id            TEXT NOT NULL REFERENCES materials(material_id),
    supplier_id            TEXT NOT NULL REFERENCES suppliers(supplier_id),
    quantity               INTEGER NOT NULL CHECK (quantity >= 0),
    order_week             INTEGER,          -- week the PO was placed (<= 0 means before the horizon)
    arrival_week           INTEGER NOT NULL CHECK (arrival_week >= 1),
    purchasing_group       TEXT NOT NULL,
    po_status              TEXT NOT NULL CHECK (po_status IN ('Open','Confirmed','Cancelled','Received')),
    cancel_allowed_until   INTEGER,          -- last week a cancellation is allowed
    maximum_defer_weeks    INTEGER NOT NULL DEFAULT 0 CHECK (maximum_defer_weeks >= 0),
    max_reduction_quantity INTEGER NOT NULL DEFAULT 0 CHECK (max_reduction_quantity >= 0),
    cancellation_fee       REAL NOT NULL DEFAULT 0 CHECK (cancellation_fee >= 0),
    reduction_fee          REAL NOT NULL DEFAULT 0 CHECK (reduction_fee >= 0),
    expedite_fee           REAL NOT NULL DEFAULT 0 CHECK (expedite_fee >= 0),
    expedited              INTEGER NOT NULL DEFAULT 0 CHECK (expedited IN (0,1))
);
CREATE INDEX idx_po_material ON purchase_orders(material_id);
CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);

-- 14. Simulation runs. simulation_id is derived from input_snapshot_hash, so a replay maps to the same row.
CREATE TABLE simulation_runs (
    simulation_id        TEXT PRIMARY KEY,
    change_id            TEXT NOT NULL REFERENCES engineering_changes(change_id),
    scenario_id          TEXT NOT NULL,
    input_snapshot_hash  TEXT NOT NULL,
    engine_version       TEXT NOT NULL,
    simulation_timestamp TEXT NOT NULL,
    simulation_status    TEXT NOT NULL CHECK (simulation_status IN ('VALID','NEEDS_REVIEW','INSUFFICIENT_DATA','INVALID')),
    total_shortage_units INTEGER CHECK (total_shortage_units IS NULL OR total_shortage_units >= 0),
    excess_value         REAL CHECK (excess_value IS NULL OR excess_value >= 0),
    rev_b_scrap_units    INTEGER,
    rev_c_closing_units  INTEGER,
    result_json          TEXT NOT NULL
);
CREATE INDEX idx_sim_change ON simulation_runs(change_id);

-- 9. Candidate plans (written by Member 2) - PROPOSED contract
CREATE TABLE candidate_plans (
    optimization_run_id     TEXT NOT NULL,
    plan_id                 TEXT NOT NULL,
    change_id               TEXT NOT NULL REFERENCES engineering_changes(change_id),
    scenario_id             TEXT NOT NULL DEFAULT 'BASE',
    simulation_id           TEXT REFERENCES simulation_runs(simulation_id),
    effective_week          INTEGER NOT NULL CHECK (effective_week >= 1),
    feasibility             TEXT NOT NULL CHECK (feasibility IN ('FEASIBLE','REJECTED')),
    shortage_units          INTEGER CHECK (shortage_units IS NULL OR shortage_units >= 0),
    excess_value            REAL CHECK (excess_value IS NULL OR excess_value >= 0),
    action_cost             REAL CHECK (action_cost IS NULL OR action_cost >= 0),
    secondary_cost          REAL CHECK (secondary_cost IS NULL OR secondary_cost >= 0),   -- E + C
    plan_rank               INTEGER CHECK (plan_rank IS NULL OR plan_rank >= 1),
    near_tie_group          TEXT,
    robustness_numerator    INTEGER CHECK (robustness_numerator IS NULL OR robustness_numerator >= 0),
    robustness_denominator  INTEGER CHECK (robustness_denominator IS NULL OR robustness_denominator > 0),
    rejection_reasons_json  TEXT NOT NULL DEFAULT '[]',
    created_at              TEXT NOT NULL,
    PRIMARY KEY (optimization_run_id, plan_id)
);

-- 10. Plan actions (written by Member 2) - PROPOSED contract
CREATE TABLE plan_actions (
    action_id           TEXT PRIMARY KEY,                  -- e.g. OPT-1:P1:A1
    optimization_run_id TEXT NOT NULL,
    plan_id             TEXT NOT NULL,
    action_type         TEXT NOT NULL CHECK (action_type IN (
                          'CONTINUE_REV_B','SHIFT_EFFECTIVE_WEEK','REDUCE_REV_B_PO','CANCEL_REV_B_PO',
                          'DEFER_REV_B_PO','EXPEDITE_REV_C_PO','DEFER_REV_C_PO','ALTERNATE_SUPPLIER')),
    po_id               TEXT REFERENCES purchase_orders(po_id),
    supplier_id         TEXT REFERENCES suppliers(supplier_id),
    quantity            INTEGER CHECK (quantity IS NULL OR quantity >= 0),
    weeks               INTEGER,
    target_week         INTEGER,
    fee                 REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
    FOREIGN KEY (optimization_run_id, plan_id) REFERENCES candidate_plans(optimization_run_id, plan_id)
);

-- 11. Exceptions (written by Member 1 severity engine; read by Members 2 and 3)
CREATE TABLE exceptions (
    simulation_id      TEXT NOT NULL REFERENCES simulation_runs(simulation_id),
    exception_id       TEXT NOT NULL,
    change_id          TEXT NOT NULL REFERENCES engineering_changes(change_id),
    exception_type     TEXT NOT NULL,
    material_id        TEXT,
    week               INTEGER,
    quantity           INTEGER,
    financial_impact   REAL NOT NULL DEFAULT 0 CHECK (financial_impact >= 0),
    severity_score     REAL NOT NULL CHECK (severity_score BETWEEN 0 AND 100),
    severity_level     TEXT NOT NULL CHECK (severity_level IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    severity_rank      INTEGER NOT NULL CHECK (severity_rank >= 1),
    description        TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    owner_role         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
    PRIMARY KEY (simulation_id, exception_id)
);
CREATE INDEX idx_exceptions_change ON exceptions(change_id);

-- 12. Action tracker (written by Member 3) - PROPOSED contract
CREATE TABLE action_tracker (
    tracker_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id    TEXT NOT NULL REFERENCES plan_actions(action_id),
    owner_role   TEXT NOT NULL,
    owner_name   TEXT,
    status       TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','In Progress','Done','Blocked','Cancelled')),
    due_week     INTEGER,
    updated_at   TEXT NOT NULL
);

-- 13. Audit log (written by Member 3). Append-only: UPDATE and DELETE are rejected by triggers.
--     event_hash = sha256(previous_hash + payload) gives a tamper-evident chain for replay.
CREATE TABLE audit_log (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time    TEXT NOT NULL,
    actor         TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    payload_json  TEXT NOT NULL,
    previous_hash TEXT,
    event_hash    TEXT NOT NULL
);
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
