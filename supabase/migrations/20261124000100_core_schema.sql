-- Manufacturing and planning data. Source: member1/database/schema.sql (SQLite), same keys and constraints.
-- Weeks are integers (W1 = 1). Money is INR in NUMERIC. Quantities are units.
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE core.materials (
    material_id      TEXT PRIMARY KEY,
    material_name    TEXT NOT NULL,
    description      TEXT,
    revision         TEXT NOT NULL CHECK (revision ~ '^Rev [A-Z]$'),
    material_type    TEXT NOT NULL CHECK (material_type IN ('FINISHED','ASSEMBLY','COMPONENT','KIT')),
    material_status  TEXT NOT NULL CHECK (material_status IN ('Active','Released','Phase-Out','Obsolete','Blocked')),
    unit_cost        NUMERIC(14,2) NOT NULL CHECK (unit_cost >= 0),
    unit_of_measure  TEXT NOT NULL DEFAULT 'EA'
);

CREATE TABLE core.engineering_changes (
    change_id          TEXT PRIMARY KEY,
    part_number        TEXT NOT NULL REFERENCES core.materials(material_id),
    new_material_id    TEXT NOT NULL REFERENCES core.materials(material_id),
    old_revision       TEXT NOT NULL,
    new_revision       TEXT NOT NULL,
    effective_week     INTEGER NOT NULL CHECK (effective_week >= 1),
    use_up_end_week    INTEGER NOT NULL CHECK (use_up_end_week >= 1),
    interchangeability BOOLEAN NOT NULL,
    reason             TEXT,
    approver           TEXT,
    approval_status    TEXT NOT NULL CHECK (approval_status IN ('Draft','Pending','Approved','Rejected')),
    approval_week      INTEGER,
    created_at         TIMESTAMP NOT NULL,   -- the source carries no time zone
    CHECK (part_number <> new_material_id),
    CHECK (old_revision <> new_revision)
);

CREATE TABLE core.bom (
    bom_id              TEXT PRIMARY KEY,
    parent_material_id  TEXT NOT NULL REFERENCES core.materials(material_id),
    child_material_id   TEXT NOT NULL REFERENCES core.materials(material_id),
    quantity_per_parent NUMERIC(14,4) NOT NULL CHECK (quantity_per_parent > 0),
    effective_from      INTEGER NOT NULL CHECK (effective_from >= 1),
    effective_to        INTEGER CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (parent_material_id <> child_material_id),
    UNIQUE (parent_material_id, child_material_id, effective_from)
);
CREATE INDEX idx_bom_child ON core.bom(child_material_id);
CREATE INDEX idx_bom_parent ON core.bom(parent_material_id);

CREATE TABLE core.inventory (
    inventory_id   TEXT PRIMARY KEY,
    material_id    TEXT NOT NULL REFERENCES core.materials(material_id),
    plant_id       TEXT NOT NULL,
    on_hand        INTEGER NOT NULL CHECK (on_hand >= 0),
    reserved       INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0 AND reserved <= on_hand),
    safety_stock   INTEGER NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
    inventory_date DATE NOT NULL,
    UNIQUE (material_id, plant_id, inventory_date)
);
CREATE INDEX idx_inventory_material ON core.inventory(material_id);

CREATE TABLE core.demand (
    demand_id         TEXT PRIMARY KEY,
    product_id        TEXT NOT NULL REFERENCES core.materials(material_id),
    material_id       TEXT NOT NULL REFERENCES core.materials(material_id),
    plant_id          TEXT NOT NULL,
    week              INTEGER NOT NULL CHECK (week >= 1),
    required_quantity INTEGER NOT NULL CHECK (required_quantity >= 0),
    UNIQUE (product_id, material_id, plant_id, week)
);
CREATE INDEX idx_demand_material_week ON core.demand(material_id, week);

CREATE TABLE core.suppliers (
    supplier_id               TEXT PRIMARY KEY,
    supplier_name             TEXT NOT NULL,
    supplier_status           TEXT NOT NULL CHECK (supplier_status IN ('Approved','Blocked','Unqualified')),
    lead_time_weeks           INTEGER CHECK (lead_time_weeks IS NULL OR lead_time_weeks >= 0),
    expedite_available        BOOLEAN NOT NULL DEFAULT FALSE,
    expedited_lead_time_weeks INTEGER CHECK (expedited_lead_time_weeks IS NULL OR expedited_lead_time_weeks >= 0),
    expedite_fee              NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (expedite_fee >= 0),
    restriction_note          TEXT
);

CREATE TABLE core.planning_groups (
    group_id             TEXT NOT NULL,
    group_name           TEXT NOT NULL,
    material_id          TEXT NOT NULL REFERENCES core.materials(material_id),
    supplier_id          TEXT NOT NULL REFERENCES core.suppliers(supplier_id),
    authorization_status TEXT NOT NULL CHECK (authorization_status IN ('Authorized','Unauthorized')),
    PRIMARY KEY (group_id, material_id, supplier_id)
);

CREATE TABLE core.purchase_orders (
    po_id                  TEXT PRIMARY KEY,
    material_id            TEXT NOT NULL REFERENCES core.materials(material_id),
    supplier_id            TEXT NOT NULL REFERENCES core.suppliers(supplier_id),
    quantity               INTEGER NOT NULL CHECK (quantity >= 0),
    order_week             INTEGER,
    arrival_week           INTEGER NOT NULL CHECK (arrival_week >= 1),
    purchasing_group       TEXT NOT NULL,
    po_status              TEXT NOT NULL CHECK (po_status IN ('Open','Confirmed','Cancelled','Received')),
    cancel_allowed_until   INTEGER,
    maximum_defer_weeks    INTEGER NOT NULL DEFAULT 0 CHECK (maximum_defer_weeks >= 0),
    max_reduction_quantity INTEGER NOT NULL DEFAULT 0 CHECK (max_reduction_quantity >= 0),
    cancellation_fee       NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (cancellation_fee >= 0),
    reduction_fee          NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (reduction_fee >= 0),
    expedite_fee           NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (expedite_fee >= 0),
    expedited              BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_po_material ON core.purchase_orders(material_id);
CREATE INDEX idx_po_supplier ON core.purchase_orders(supplier_id);

CREATE TABLE core.simulation_runs (
    simulation_id        TEXT PRIMARY KEY,   -- derived from input_snapshot_hash, so a replay maps to the same row
    change_id            TEXT NOT NULL REFERENCES core.engineering_changes(change_id),
    scenario_id          TEXT NOT NULL,
    input_snapshot_hash  TEXT NOT NULL,
    engine_version       TEXT NOT NULL,
    simulation_timestamp TIMESTAMPTZ NOT NULL,
    simulation_status    TEXT NOT NULL CHECK (simulation_status IN ('VALID','NEEDS_REVIEW','INSUFFICIENT_DATA','INVALID')),
    total_shortage_units INTEGER CHECK (total_shortage_units IS NULL OR total_shortage_units >= 0),
    excess_value         NUMERIC(16,2) CHECK (excess_value IS NULL OR excess_value >= 0),
    rev_b_scrap_units    INTEGER,
    rev_c_closing_units  INTEGER,
    result_json          JSONB NOT NULL
);
CREATE INDEX idx_sim_change ON core.simulation_runs(change_id, scenario_id, simulation_timestamp DESC);

CREATE TABLE core.exceptions (
    simulation_id      TEXT NOT NULL REFERENCES core.simulation_runs(simulation_id),
    exception_id       TEXT NOT NULL,
    change_id          TEXT NOT NULL REFERENCES core.engineering_changes(change_id),
    exception_type     TEXT NOT NULL,
    material_id        TEXT,
    week               INTEGER,
    quantity           INTEGER,
    financial_impact   NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (financial_impact >= 0),
    severity_score     NUMERIC(5,1) NOT NULL CHECK (severity_score BETWEEN 0 AND 100),
    severity_level     TEXT NOT NULL CHECK (severity_level IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    severity_rank      INTEGER NOT NULL CHECK (severity_rank >= 1),
    description        TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    owner_role         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (simulation_id, exception_id)
);
CREATE INDEX idx_exceptions_change ON core.exceptions(change_id);

-- Proposed plans of a planning run: recommended, rejected and planner-modified ones. The full ranked list
-- stays in app.planning_runs.result, which is the authoritative record of the run.
CREATE TABLE core.candidate_plans (
    optimization_run_id     TEXT NOT NULL,
    plan_id                 TEXT NOT NULL,
    change_id               TEXT NOT NULL REFERENCES core.engineering_changes(change_id),
    scenario_id             TEXT NOT NULL DEFAULT 'BASE',
    simulation_id           TEXT REFERENCES core.simulation_runs(simulation_id),
    source                  TEXT NOT NULL DEFAULT 'ENGINE',
    effective_week          INTEGER CHECK (effective_week IS NULL OR effective_week >= 1),
    feasibility             TEXT NOT NULL CHECK (feasibility IN ('FEASIBLE','REJECTED')),
    shortage_units          INTEGER CHECK (shortage_units IS NULL OR shortage_units >= 0),
    excess_value            NUMERIC(16,2) CHECK (excess_value IS NULL OR excess_value >= 0),
    action_cost             NUMERIC(16,2) CHECK (action_cost IS NULL OR action_cost >= 0),
    secondary_cost          NUMERIC(16,2) CHECK (secondary_cost IS NULL OR secondary_cost >= 0),
    plan_rank               INTEGER CHECK (plan_rank IS NULL OR plan_rank >= 1),
    near_tie_group          TEXT,
    robustness_numerator    INTEGER CHECK (robustness_numerator IS NULL OR robustness_numerator >= 0),
    robustness_denominator  INTEGER CHECK (robustness_denominator IS NULL OR robustness_denominator > 0),
    rejection_reasons_json  JSONB NOT NULL DEFAULT '[]',
    created_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (optimization_run_id, plan_id)
);

-- An action the engine proposes. It is not a task until a planner approves it (app.action_items).
CREATE TABLE core.plan_actions (
    action_id           TEXT PRIMARY KEY,   -- <run>:<plan>:A<n>
    optimization_run_id TEXT NOT NULL,
    plan_id             TEXT NOT NULL,
    action_type         TEXT NOT NULL CHECK (action_type IN (
                          'CONTINUE_REV_B','SHIFT_EFFECTIVE_WEEK','REDUCE_REV_B_PO','CANCEL_REV_B_PO',
                          'DEFER_REV_B_PO','EXPEDITE_REV_C_PO','DEFER_REV_C_PO','ALTERNATE_SUPPLIER',
                          'CREATE_REV_B_PO')),   -- CREATE_REV_B_PO appears only in rejected probe plans
    po_id               TEXT REFERENCES core.purchase_orders(po_id),
    supplier_id         TEXT REFERENCES core.suppliers(supplier_id),
    quantity            INTEGER CHECK (quantity IS NULL OR quantity >= 0),
    weeks               INTEGER,
    target_week         INTEGER,
    fee                 NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (fee >= 0),
    FOREIGN KEY (optimization_run_id, plan_id) REFERENCES core.candidate_plans(optimization_run_id, plan_id)
);
CREATE INDEX idx_plan_actions_plan ON core.plan_actions(optimization_run_id, plan_id);
