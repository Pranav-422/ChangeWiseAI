# MVP acceptance report

24 November 2026, branch `migration/vercel-render-supabase-gemini`. Evidence: CI run
https://github.com/Pranav-422/ChangeWiseAI/actions/runs/45440236116 (all five jobs green) and local runs on Windows.

## Verdict

**The MVP is not accepted yet.** Everything that can be built and tested without cloud accounts is done and passes, including on the real
Supabase stack in CI. Three things are missing because they need credentials nobody but the project owner may enter: a hosted Supabase
project, the Render service, and a Gemini key. Steps: `DEPLOYMENT.md`.

## Repository and source

* Member 1 and Member 2: no file changed. Member 3: small hooks and the provider; listed in `COMPONENT_INVENTORY.md`.
* New: `backend/`, `frontend/`, `supabase/`, `scripts/`, `shared/`, `docs/migration/`, `render.yaml`, CI.
* Not merged. `main` is untouched. The Streamlit application still works and its tests run.

## Test evidence

| Suite | Where | Result |
|---|---|---|
| Member 1 | CI, Ubuntu, Python 3.12 | 123 passed |
| Member 1 | Windows computer | 120 passed, 3 failed (PyMuPDF blocked, as before the migration) |
| Member 2 and Member 3 | CI | 551 passed |
| Backend (API, security, RLS, migration, parity, Gemini SDK) | CI, PostgreSQL 17 | 115 passed |
| Frontend unit and component | CI | 36 passed; lint, type check and production build clean |
| End to end, local stand-in for Supabase | Windows, Chrome | 21 passed, 1 skipped (needs the real stack) |
| End to end, real Supabase stack (PostgreSQL 17.12, Auth, Storage, mail) | CI, Chromium | 21 passed, 1 skipped (needs the stand-in) |
| RLS, roles, bucket and REST exposure on the real stack | CI | every check passed |
| Data migration, value by value | CI real stack, local PostgreSQL 16 | PASS, 0 missing, 0 different |

## Database

| Item | State |
|---|---|
| Hosted Supabase project | **BLOCKED**: needs the owner's account |
| Five migrations on the real Supabase stack | done (CI) |
| Sources backed up read-only with checksums | done; `backups/`, not committed |
| Rows | 49 Member 1 rows migrated, IDs unchanged; Member 3's local database is empty. A complete Member 3 workflow was migrated in a test: chain intact, replay matches, new events continue the chain |
| Foreign keys | 32, all validated |
| RLS | on for every table; verified per role on the real stack |
| Storage | private bucket; verified on the real stack |

## Backend

| Item | State |
|---|---|
| Render URL | **BLOCKED**: not deployed |
| `/health`, `/ready` | pass locally and in CI in production mode |
| Routes | 55 operations; every protected one refuses a missing token |
| Token verification | ES256/RS256 by JWKS, issuer, audience, expiry; HS256, `none`, anonymous, other key refused |
| Production SQLite dependency | none |

## Frontend

| Item | State |
|---|---|
| Vercel | project `changewise-ai` created; preview builds and is Ready: https://changewise-8f65p2hs3-unhinged1.vercel.app (Vercel login required). It shows "Not configured yet", because Supabase and Render values do not exist |
| Production deployment | **BLOCKED** by the same |
| Pages | 14 workspace routes and 5 sign-in routes |
| Responsive | no horizontal overflow on any page at 1440, 1180, 820, 390 (test) |
| Keyboard | skip link, tabs, chart weeks, quick jump, native dialogs (test) |
| Secrets in the bundle | none (test) |

## AI

| Item | State |
|---|---|
| Model | `gemini-3.8-flash` by default (`gemini-2.5-flash` ends 1 December 2026) |
| Live test | **NOT TESTED**: no key. `python -m scripts.migration.live_gemini_check` runs eight checks and writes the result |
| SDK request format, retries, failures, key never in an error | pass, real SDK against a local server |
| Extraction, what-if, explanation with offline rules and templates | pass |
| Grounding, claim verifier, fallback | pass with a fake provider: an ungrounded value is dropped, a wrong claim is never shown |

## Business logic

Objective, seven rules, near-tie, nine stress runs, baselines and replay: unchanged code, identical output in all six scenarios
(`BASELINE_PARITY_REPORT.md`). Test doubles cannot be selected by the backend.

## Demonstrations

| # | Demonstration | Local and CI | Deployed |
|---|---|---|---|
| 1 | Sign in, role, protected pages | pass | blocked |
| 2 | PDF upload to private storage, extraction, quotes, correction | pass (offline rules) | blocked |
| 3 | Validation and confirmation | pass | blocked |
| 4 | BOM impact | pass | blocked |
| 5 | Inventory simulation W1 to W8 | pass | blocked |
| 6 | Optimization, rejected plans, near-tie, robustness | pass | blocked |
| 7 | What-if: one week late and demand +10% | pass | blocked |
| 8 | Approval with required comment | pass | blocked |
| 9 | Action tracker and history | pass | blocked |
| 10 | Audit and replay | pass | blocked |
| 11 | Persistence after sign out and restart | pass | blocked |

## End-to-end scenarios of the brief

1 complete workflow, 2 missing fields, 3 ambiguous, 4 conflicting revision, 5 invalid data, 6 base case, 7 and 8 delay and demand what-if,
9 blocked supplier, 10 no feasible plan, 11 near-tie, 12 rejection, 13 modification, 14 action progression, 15 replay, 16 Gemini
unavailable, 17 expired session, 18 unauthorized role, 19 Supabase unavailable, 20 duplicate approval: each is covered by a backend test,
an end-to-end test, or both.

## Checklist

| Area | Done | Blocked |
|---|---|---|
| Business logic (10) | 10 | 0 |
| Database (12) | 11 | hosted project, so "production persistence uses Supabase" is proven only on the local stack |
| Backend (8) | 8 | 0 |
| AI (10) | 9 | live verification |
| Frontend (17) | 17 | 0 |
| Deployment (10) | 1 (Vercel build) | 9 |
| Testing (7) | 7 | 0 |

## Known limitations

`KNOWN_ISSUES.md`. The most important: no live Gemini call has been made; the audit chain is tamper-evident, not tamper-proof; one writer at
a time; no OCR; team decisions on near-tie and planning-week readings are open.
