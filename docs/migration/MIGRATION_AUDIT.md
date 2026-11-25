# Migration audit

State inspected: commit `d562da2` (`main`, pull requests 1 to 3 merged), 24 November 2026. Work branch:
`migration/vercel-render-supabase-gemini`. The branch name is older than the decision to host the API on Vercel instead of Render.

## Entry points before the migration

| Part | Entry point | Store |
|---|---|---|
| Member 1 | `python scripts/run_pipeline.py` (from `member1/`), `dashboard/*.py` (Streamlit views) | `member1/database/changewise.db`, `member1/data/synthetic/*.csv` |
| Member 2 | `member2.engine.pipeline.run_optimization`, `streamlit run member2/dashboard/app.py`, `python -m member2.evaluation.run_all` | none |
| Member 3 | `streamlit run member3/application/app.py` | `member3/data/app.db` (`CHANGEWISE_DB` overrides) |

## Module dependencies

* Member 1 imports nothing from the others. Run as `engine.*` from its own folder and as `member1.engine.*` from the root.
* Member 2 imports Member 1 only in `member2/integration/member1_bridge.py`.
* Member 3 imports Member 2 in `services/member2_adapter.py`, `services/action_tracker_service.py`, `ai/fallback_templates.py`
  and `components/`; it imports Member 1 only in `integration/member1_module.py`.
* Test doubles: `member2/reference/`, `member3/reference/`. No production module imports them. The adapter can load one when
  `CHANGEWISE_MEMBER1` names it, so the cloud backend passes the module name itself and ignores that variable.

## Tables and owners

* Member 1 schema, 14 tables: 8 input tables (read), `simulation_runs` and `exceptions` (written by Member 1),
  `candidate_plans`, `plan_actions`, `action_tracker`, `audit_log` (proposed for Members 2 and 3, empty in practice).
* Member 3 schema, 6 tables: `ecn_reviews`, `planning_runs`, `what_if_requests`, `approvals`, `action_items`, `audit_log`.
* Rows found: Member 1 has 50 rows in 10 tables; Member 3's local database is empty and is not in Git.

## Overlaps found and how they were resolved

| Overlap | Resolution |
|---|---|
| `plan_actions` / `action_items` / `action_tracker` | Proposed actions stay in `core.plan_actions`; tasks in `app.action_items`, linked by `plan_action_id`; status in `app.action_status_history`. `action_tracker` is superseded and not created. |
| Two `audit_log` tables | `app.audit_log` is the live chain. Member 1's rows go unchanged to `app.legacy_audit_events`. `app.audit_events` shows both. |
| Planning data in CSV and SQLite | PostgreSQL `core.*` is the only production source. The CSV files stay for tests and for the old application. |

## Assumptions tied to a local file system

* `member3.database.connection` opened a SQLite path. It now accepts another store (`use()`); SQLite stays the default.
* `member3.integration.member1_module` read CSV files. Its functions now accept tables.
* ECN PDFs were read from `member1/documents/ecn_samples`. They remain there as samples; uploads go to Supabase Storage.
  The upload limit is 4 MB, because a Vercel function accepts a request body of at most 4.5 MB.
* Streamlit session state held the role and the selected scenario. Replaced by Supabase Auth and a browser preference.

## Assumptions tied to one long-running process

* The run cache and the connection pool are in process memory. On Vercel each function instance has its own.
* Writers were serialised by SQLite. An advisory lock in PostgreSQL serialises them now, across instances.
* Database code is transaction-local, so it works behind the Supabase transaction pooler.

## Generated data

`member1/data/generated/*` and `member*/reports/*` are outputs. Nothing in the cloud path reads them.

## Gemini before the migration

Direct HTTPS call with `urllib`, model `gemini-2.5-flash`. That model's earliest shutdown date is 1 December 2026, so the default
is now `gemini-3.8-flash` (a stable model on Google's list on 24 November 2026). It is named once, in
`member3/config/settings.yaml`; `GEMINI_MODEL` overrides it.

## Preserve, replace, extend

* **Preserve:** every file of `member1/engine`, `member2/engine`, `member2/solver`, `member2/evaluation`, and Member 3's extraction,
  validation, verifier, templates and service rules.
* **Replace in production:** Streamlit pages and components, the sidebar role, SQLite persistence.
* **Extend:** provider (SDK, schema, usage log), three small hooks in Member 3 (`connection.use`, `on_stored` in planning and
  approval). See `COMPONENT_INVENTORY.md` for the full list of touched lines.
