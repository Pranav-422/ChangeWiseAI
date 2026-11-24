-- Application records. Member 1's planning data is never written here or anywhere else.
CREATE TABLE IF NOT EXISTS ecn_reviews (
    review_id      TEXT PRIMARY KEY,
    scenario_id    TEXT NOT NULL,
    document_text  TEXT NOT NULL,
    document_hash  TEXT NOT NULL,
    extraction     TEXT NOT NULL,   -- JSON, as extracted, never edited
    fields         TEXT NOT NULL,   -- JSON, as edited by the planner
    validation     TEXT NOT NULL,   -- JSON
    status         TEXT NOT NULL CHECK (status IN ('NEEDS_REVIEW', 'CONFIRMED')),
    created_by     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    confirmed_by   TEXT,
    confirmed_at   TEXT
);

CREATE TABLE IF NOT EXISTS planning_runs (
    run_id       TEXT PRIMARY KEY,
    review_id    TEXT NOT NULL REFERENCES ecn_reviews (review_id),
    scenario_id  TEXT NOT NULL,
    input_hash   TEXT NOT NULL,
    decision     TEXT NOT NULL,
    dataset      TEXT NOT NULL,     -- JSON snapshot used for replay
    config       TEXT NOT NULL,     -- JSON snapshot used for replay
    result       TEXT NOT NULL,     -- JSON, Member 2 output
    context      TEXT NOT NULL,     -- JSON: baseline simulation, exceptions, BOM impact (Member 1 output)
    explanation  TEXT NOT NULL,     -- JSON, with its verification record
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS what_if_requests (
    request_id  TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES planning_runs (run_id),
    question    TEXT NOT NULL,
    parameters  TEXT NOT NULL,
    result      TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id  TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL UNIQUE REFERENCES planning_runs (run_id),  -- one final decision per run
    decision     TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
    modified     INTEGER NOT NULL DEFAULT 0,
    plan         TEXT,              -- JSON of the approved plan
    comment      TEXT NOT NULL,
    user_name    TEXT NOT NULL,
    role         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    closed_at    TEXT
);

CREATE TABLE IF NOT EXISTS action_items (
    action_id    TEXT PRIMARY KEY,
    approval_id  TEXT NOT NULL REFERENCES approvals (approval_id),
    run_id       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    action       TEXT NOT NULL,
    owner_role   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('OPEN', 'IN_PROGRESS', 'DONE')),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- Append-only and hash-chained: each row's hash covers the previous row's hash.
CREATE TABLE IF NOT EXISTS audit_log (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    user_name      TEXT NOT NULL,
    role           TEXT NOT NULL,
    payload        TEXT NOT NULL,
    previous_hash  TEXT NOT NULL,
    event_hash     TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
