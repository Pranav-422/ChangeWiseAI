# ChangeWise AI

Engineering change intelligence and phase-in/phase-out control. Team TG10, TECHgium 10th Edition.

The engine calculates and decides. The AI interprets and explains. The planner approves.

| Folder | What it is |
|---|---|
| `member1/` | Data, validation, BOM impact, weekly inventory simulation, severity |
| `member2/` | Candidate plans, seven hard rules, lexicographic optimization, robustness, baselines |
| `member3/` | ECN extraction, what-if parsing, verified explanations, workflow services, earlier Streamlit application |
| `backend/` | FastAPI service that runs the three modules on PostgreSQL (Render) |
| `frontend/` | Next.js application (Vercel) |
| `supabase/` | Versioned PostgreSQL migrations, RLS, storage |
| `scripts/` | Data migration, parity checks, local stack |
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
