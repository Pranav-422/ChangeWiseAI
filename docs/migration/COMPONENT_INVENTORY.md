# Component inventory

## Existing code changed by the migration

| File | Change |
|---|---|
| `member3/database/connection.py` | `use(factory)` sends `transaction()` to another store; SQLite stays the default |
| `member3/services/planning_service.py` | optional `on_stored(db, run)` inside the storing transaction |
| `member3/services/approval_service.py` | optional `on_stored(db, approval_id, plan)` inside the decision transaction; `modified` stored as a boolean |
| `member3/integration/member1_module.py` | `validate_ecn` and `bom_impact` accept tables; `load_tables()` |
| `member3/ai/provider.py` | Google Gen AI SDK behind the same `complete_json` interface, optional JSON schema |
| `member3/ai/ecn_extractor.py`, `what_if_parser.py`, `explanation_generator.py` | pass their JSON schema to the provider |
| `member3/config/settings.yaml` | current Gemini model |
| `member3/requirements.txt` | `google-genai` |
| `member3/tests/conftest.py`, `test_ecn_extraction.py` | follow the provider interface |

No file of Member 1 or Member 2 was changed.

## New

| Path | Purpose |
|---|---|
| `backend/app/core` | settings, PostgreSQL, errors, logs, request middleware |
| `backend/app/security` | token verification, roles and permissions |
| `backend/app/integrations` | Member 1 on PostgreSQL tables, Supabase Storage |
| `backend/app/services` | orchestration per domain; no calculation |
| `backend/app/api/v1`, `schemas` | 55 operations and their models |
| `backend/tests` | API, security, database, parity, Gemini SDK |
| `supabase/migrations` | 5 versioned migrations; `tests/local_stub.sql` for a plain PostgreSQL |
| `scripts/migration` | baseline capture, backup, export, import, verification, rollback notes |
| `scripts/dev` | local stack, Supabase stand-in (never deployed), CI seed and checks |
| `frontend/components/ui` | buttons, fields, dialog, drawer, tabs, menu, tooltip, table, status, alert, empty, error, skeleton |
| `frontend/components/*` | Revision Ribbon, Material Flow, Inventory charts, BOM Lineage, Decision Panel, Severity Rail, Audit Timeline, Explanation Panel, Robustness Matrix |
| `shared/api-contracts` | OpenAPI document and contract |
| `render.yaml`, `.github/workflows/ci.yml` | deployment and CI |

## Kept for comparison

The Streamlit application and both SQLite paths still work and their tests still run in CI.
