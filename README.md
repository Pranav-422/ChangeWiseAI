# ChangeWise AI

Engineering change intelligence and phase-in/phase-out control. Team TG10, TECHgium 10th Edition.

The engine calculates and decides. The AI interprets and explains. The planner approves.

## Live deployment

| Part | Link |
|---|---|
| Application | https://changewise-ai.vercel.app |
| API | https://changewise-api.vercel.app ([health](https://changewise-api.vercel.app/health), [readiness](https://changewise-api.vercel.app/ready)) |

Sign in with an account, or choose **Continue as guest**: a guest can view the planning data and change nothing.

Status on 25 November 2026: both parts are online. The hosted database is not loaded and guest access is not yet switched
on in Supabase, so the pages after sign-in have no data. Readiness shows `"status":"ready"` when that is finished.

Next.js on Vercel, FastAPI on Vercel, PostgreSQL, Auth and Storage on Supabase (Mumbai), Gemini for text only. Without a
Gemini key the application uses its own templates.

## Repository

| Folder | What it is |
|---|---|
| `member1/` | Data, validation, BOM impact, weekly inventory simulation, severity |
| `member2/` | Candidate plans, seven hard rules, lexicographic optimization, robustness, baselines |
| `member3/` | ECN extraction, what-if parsing, verified explanations, workflow services, earlier Streamlit application |
| `backend/` | FastAPI service that runs the three modules on PostgreSQL (Vercel project `changewise-api`) |
| `frontend/` | Next.js application (Vercel project `changewise-ai`) |
| `index.py`, `requirements.txt`, `vercel.json`, `.vercelignore` | Vercel entrypoint, dependencies and settings of the API |
| `supabase/` | Versioned PostgreSQL migrations, RLS, storage |
| `scripts/` | Data migration, parity checks, local stack, cloud setup |
| `shared/api-contracts/` | OpenAPI contract |
| `docs/migration/` | Audit, design system, reports, deployment guide |

## Run it on this computer

Python 3.12 and Node 24. No cloud account is needed.

```powershell
py -3.12 -m venv .venv
```

```powershell
.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
```

```powershell
.venv\Scripts\python -m scripts.dev.run_local --reset
```

In a second terminal:

```powershell
npm --prefix frontend ci
```

```powershell
Copy-Item frontend/.env.example frontend/.env.local
```

```powershell
npm --prefix frontend run dev
```

Open http://localhost:3000. Test accounts are in `scripts/dev/accounts.py`.

## Test it

```powershell
.venv\Scripts\python -m pytest backend
```

```powershell
npm --prefix frontend test
```

`bash scripts/dev/e2e_local.sh` runs every end-to-end test on a fresh stack. CI also runs them on the real Supabase stack.

## Deploy it

[docs/migration/DEPLOYMENT.md](docs/migration/DEPLOYMENT.md). State of acceptance:
[docs/migration/FINAL_MVP_ACCEPTANCE_REPORT.md](docs/migration/FINAL_MVP_ACCEPTANCE_REPORT.md).

All planning data in this repository is synthetic.
