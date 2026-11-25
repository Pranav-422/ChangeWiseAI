# Deployment

Two Vercel projects use this one repository. The database, sign-in and file storage are in Supabase.

| Project | Root | What it runs |
|---|---|---|
| Vercel `changewise-ai` | `frontend` | Next.js |
| Vercel `changewise-api` | repository root | Python 3.12, FastAPI |
| Supabase `changewise` | ref `feocfauwwjgbugbqakhi` | PostgreSQL, Auth, Storage; region ap-south-1 (Mumbai), free plan |

Order matters: Supabase, then the API, then the frontend, then the settings that need the final URLs.
No secret belongs in this repository, in a file, in a `NEXT_PUBLIC_*` variable, or in a chat.

## 1. Supabase

The project `changewise` exists. It is empty until you run the setup script.

1. Project Settings > Database: reset the database password. Keep it.
2. Connect > Transaction pooler: copy the connection string (port 6543, user `postgres.<ref>`). Percent-encode special characters of the
   password.
3. Project Settings > API keys: note the publishable key and a secret key (`sb_secret_...`). Settings > JWT keys must show an asymmetric
   key (ES256), which is the default of new projects. The backend refuses HS256 tokens.
4. Authentication > Providers > Email: on, confirm email on, minimum password length 8.
   Authentication > Sign In / Providers: allow anonymous sign-ins on. It is the "Continue as guest" button;
   a guest is always a viewer.
5. Storage needs no step: the migration creates the private bucket `ecn-documents` and its policy. The bucket limit is 10 MiB.

## 2. Run the setup script

Run it in your own terminal, in the repository root. The Vercel CLI must be signed in, and the folder must be linked to
`changewise-api`.

```powershell
.venv\Scripts\python -m scripts.deploy.setup_cloud
```

A window asks for three values. The fields are masked.

| Value | Where it comes from |
|---|---|
| Database password | section 1, step 2 |
| Supabase secret key | `sb_secret_...`, section 1, step 3 |
| Gemini key | optional |

The script then:

* applies the migrations,
* loads and verifies the data; the sources are only read,
* stores the secrets as production environment variables of `changewise-api` through the Vercel CLI.

It writes no secret to a file and prints none.

### The same database steps by hand

Use these only if you do not use the script. Put the connection string in a private PowerShell window, never in a chat or a file:

```powershell
$env:DATABASE_URL = Read-Host "Transaction pooler string"
```

On the computer where Application Control blocks native files, also run this once in the same window (the setup script does this itself):

```powershell
$env:PATH = "$PWD\.venv\Lib\site-packages\pixeltable_pgserver\pginstall\bin;$env:PATH"
```

Apply the migrations. Where the Supabase CLI runs, `supabase link` and `supabase db push` do the same; on the computer with Application
Control it is blocked. `supabase/config.toml` is for the local stack. Do not run `supabase config push`.

```powershell
.venv\Scripts\python -m scripts.migration.apply_migrations
```

Load and verify the data:

```powershell
.venv\Scripts\python -m scripts.migration.export_sqlite
```

```powershell
.venv\Scripts\python -m scripts.migration.import_postgres backups\<time>\export.json
```

```powershell
.venv\Scripts\python -m scripts.migration.verify_migration backups\<time>\export.json --where "Supabase project"
```

## 3. Vercel: `changewise-api`

The project root is the repository root, because the API imports `member1`, `member2` and `member3`.

* `index.py` is the entrypoint. It re-exports `backend.app.main:app`.
* `requirements.txt` in the repository root lists the dependencies. It replaced `backend/requirements.txt`.
* `vercel.json` holds the settings, with region `bom1` (Mumbai).
* `.vercelignore` leaves out the frontend, the tests and the docs.

Environment variables for Production:

| Variable | Value | Set by |
|---|---|---|
| `DATABASE_URL` | transaction pooler string | setup script |
| `SUPABASE_SECRET_KEY` | `sb_secret_...` (`SUPABASE_SERVICE_ROLE_KEY` is accepted for a legacy key) | setup script |
| `GEMINI_API_KEY` | optional | setup script |
| `SUPABASE_URL` | `https://feocfauwwjgbugbqakhi.supabase.co` | assistant |
| `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_...` | assistant |
| `ENVIRONMENT` | `production` | assistant |
| `FRONTEND_ORIGIN` | the frontend URL, no trailing slash; several values separated by commas | assistant |
| `DB_POOL_SIZE` | `3` | assistant |
| `GEMINI_MODEL` | optional; leave it empty for the default | you |

A changed variable applies to the next deployment, so deploy after the setup script has run.
Check `https://<api>/ready`, where `<api>` is the host of `changewise-api`: `database`, `auth` and `storage` must be true.

Limits on the Hobby plan: 300 s maximum duration, 2 GB memory, 500 MB Python bundle. A function accepts a request body of at most
4.5 MB, so the upload limit is 4 MB. The first request after a quiet period is a cold start of some seconds.

The run cache and the connection pool belong to one function instance. The advisory lock in PostgreSQL serialises writers across
instances. The code is transaction-local, so it works behind the transaction pooler.

## 4. Vercel: `changewise-ai`

The project exists (created from the command line, root `frontend/`).

1. Settings > Git: connect the repository. Settings > General: Root Directory `frontend`, framework Next.js.
2. Settings > Environment Variables, for Production and Preview. The assistant sets these three, and nothing else belongs here:
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL` (the URL of `changewise-api`).
3. Deploy. The values are built in, so a change needs a new deployment.

## 5. Join them

1. `changewise-api`: `FRONTEND_ORIGIN` must be the production URL of `changewise-ai`. Deploy again after a change.
2. Supabase > Authentication > URL configuration: Site URL = the Vercel frontend URL; Redirect URL = `https://<frontend>/**`.
3. Sign up in the application, then make that account the first administrator in the Supabase SQL editor:

   ```sql
   UPDATE app.user_profiles SET role='ADMIN' WHERE email='<your address>';
   ```

   Everyone else gets a role in Settings > Access.

## 6. Verify

* The eleven demonstrations in `FINAL_MVP_ACCEPTANCE_REPORT.md`, on the deployed URLs.
* Gemini, once a key is set: `$env:GEMINI_API_KEY="..."` in a private shell, then `python -m scripts.migration.live_gemini_check`. It writes
  `GEMINI_LIVE_TEST.md` with what happened.

## Alternative: Render

`render.yaml` defines `changewise-api` for Render. It is not tested.

1. Open https://dashboard.render.com/blueprint/new?repo=https://github.com/Pranav-422/ChangeWiseAI and choose the branch
   `migration/vercel-render-supabase-gemini`. The service root is the repository root. The blueprint uses region Singapore; the database
   is in Mumbai.
2. Enter the values it asks for. They are those of section 3, except that `DATABASE_URL` is the session pooler string (Connect > Session
   pooler, port 5432). It works over IPv4, which Render needs on the Free plan.
3. Check `https://<service>.onrender.com/ready`.
4. Set `NEXT_PUBLIC_API_BASE_URL` of `changewise-ai` to the Render URL and deploy the frontend again.

The Render free plan sleeps after 15 minutes. The first request then takes about a minute.

## Local development

```powershell
.venv\Scripts\python -m scripts.dev.run_local --reset
```

```powershell
npm --prefix frontend run dev
```

`scripts/dev/supabase_stub.py` stands in for Supabase Auth and Storage on this computer only. The full end-to-end run is
`bash scripts/dev/e2e_local.sh`.
