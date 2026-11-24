# Deployment

Order matters: Supabase, then Render, then Vercel, then the two settings that need the final URLs.
No secret belongs in this repository, in Vercel, or in a chat.

## 1. Supabase

1. Create a project at https://supabase.com/dashboard, region Singapore (the Render blueprint uses the same). Keep the database password.
2. Apply the migrations from the repository root:

   ```powershell
   npx supabase@3.4.0 login
   ```

   ```powershell
   npx supabase@3.4.0 link --project-ref <project-ref>
   ```

   ```powershell
   npx supabase@3.4.0 db push
   ```

   `supabase/config.toml` is for the local stack. Do not run `supabase config push`.
3. Connect > Session pooler: copy the connection string (port 5432, user `postgres.<ref>`). It works over IPv4, which Render needs on
   the Free plan. Percent-encode special characters of the password.
4. Load and verify the data. The sources are only read.

   ```powershell
   $env:DATABASE_URL = "<session pooler string>"
   ```

   ```powershell
   .venv\Scripts\python -m scripts.migration.export_sqlite
   ```

   ```powershell
   .venv\Scripts\python -m scripts.migration.import_postgres backups\<time>\export.json
   ```

   ```powershell
   .venv\Scripts\python -m scripts.migration.verify_migration backups\<time>\export.json --where "Supabase project"
   ```

   On the computer where Application Control blocks `psycopg_binary`, first put the embedded server's libraries on the path:
   `$env:PATH = "$PWD\.venv\Lib\site-packages\pixeltable_pgserver\pginstall\bin;$env:PATH"`.
5. Authentication > Providers > Email: on, confirm email on, minimum password length 8.
6. Project Settings > API keys: note the publishable key and a secret key. Settings > JWT keys must show an asymmetric key (ES256), which
   is the default of new projects. The backend refuses HS256 tokens.
7. Storage needs no step: the migration creates the private bucket `ecn-documents` and its policy.

## 2. Render

1. New > Blueprint, choose the repository and the branch. `render.yaml` defines `changewise-api`. The service root is the repository root.
2. Enter the values it asks for:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | session pooler string |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_...` |
   | `SUPABASE_SECRET_KEY` | `sb_secret_...` (`SUPABASE_SERVICE_ROLE_KEY` is accepted for a legacy key) |
   | `FRONTEND_ORIGIN` | the Vercel URL, no trailing slash; several values separated by commas |
   | `GEMINI_API_KEY`, `GEMINI_MODEL` | optional; leave `GEMINI_MODEL` empty for the default |

3. Check `https://<service>.onrender.com/ready`: `database`, `auth` and `storage` are true.

## 3. Vercel

The project `changewise-ai` exists (created from the command line, root `frontend/`).

1. Settings > Git: connect the repository. Settings > General: Root Directory `frontend`, framework Next.js.
2. Settings > Environment Variables, for Production and Preview:
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_BASE_URL` (the Render URL). Nothing else.
3. Deploy. The values are built in, so a change needs a new deployment.

## 4. Join them

1. Render: set `FRONTEND_ORIGIN` to the Vercel production URL.
2. Supabase > Authentication > URL configuration: Site URL = the Vercel URL; Redirect URLs = `https://<vercel-url>/**`.
3. Sign up in the application, then make that account the first administrator in the Supabase SQL editor:

   ```sql
   UPDATE app.user_profiles SET role = 'ADMIN' WHERE email = '<your address>';
   ```

   Everyone else gets a role in Settings > Access.

## 5. Verify

* The eleven demonstrations in `FINAL_MVP_ACCEPTANCE_REPORT.md`, on the deployed URLs.
* Gemini, once a key is set: `$env:GEMINI_API_KEY="..."` in a private shell, then `python -m scripts.migration.live_gemini_check`. It writes
  `GEMINI_LIVE_TEST.md` with what happened.

## Local development

```powershell
.venv\Scripts\python -m scripts.dev.run_local --reset
```

```powershell
npm --prefix frontend run dev
```

`scripts/dev/supabase_stub.py` stands in for Supabase Auth and Storage on this computer only. The full end-to-end run is
`bash scripts/dev/e2e_local.sh`.
