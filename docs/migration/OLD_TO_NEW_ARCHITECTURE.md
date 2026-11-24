# From the old architecture to the new one

```
Browser -- HTTPS --> Vercel (Next.js: pages, session cookie, security headers)
   |                        |
   | access token           | Supabase Auth (sign-in, refresh)
   v                        v
Render (FastAPI: verify token, role, request schema)
   |-- member1.engine   validation, BOM, simulation, severity     (unchanged)
   |-- member2.engine   candidates, hard rules, ranking, stress   (unchanged)
   |-- member3          extraction, verifier, workflow services   (runs on PostgreSQL)
   |-- Supabase PostgreSQL   core.* and app.*
   |-- Supabase Storage      private bucket ecn-documents
   '-- Gemini API            optional; deterministic fallback otherwise
```

| Old | New |
|---|---|
| Streamlit pages 1 to 9 | Next.js routes `/dashboard` `/ecn` `/bom` `/inventory` `/optimization` `/what-if` `/actions` `/approvals` `/audit`, plus `/engineering-changes`, `/exceptions`, `/replay`, `/settings` |
| `application/session_manager.py` | `components/layout/Workspace.tsx` |
| Sidebar role selector | Supabase Auth + `app.user_profiles.role`, set by an administrator |
| `application/access_control.py` | still the rule for Member 3's five permissions; `backend/app/security/permissions.py` adds the rest |
| SQLite, `BEGIN IMMEDIATE` | PostgreSQL, one transaction per state change, one advisory lock for writers |
| SQLite triggers on `audit_log` | PostgreSQL triggers, also on planning runs and action history, also against TRUNCATE |
| `st.file_uploader`, text in the database only | private bucket, SHA-256 checked before extraction, 60-second signed links |
| CSV tables | one SQL statement that returns the same eight tables |
| `urllib` Gemini call | Google Gen AI SDK, Interactions API, JSON schema, `store: false`, two attempts |

## Why one backend service

Member 2 calls Member 1's simulator more than a thousand times per run, and Member 3 calls both. A network hop between them would
cost seconds and add failure modes. All three stay in one Python process.

## Why the Member 3 services run unchanged on PostgreSQL

`backend/app/core/database.py` offers the part of `sqlite3.Connection` those services use: `?` placeholders, mapping rows, JSON as
text, `sqlite3.IntegrityError`. Their rules (comment required, one decision per run, stale run refused, one step at a time) therefore
exist once. The acting user is announced per transaction, and column defaults record it.

## Principle kept

The engine calculates and decides. The AI interprets and explains. The planner approves. The browser calculates nothing: it formats
values and chooses what to show.
