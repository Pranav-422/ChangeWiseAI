"""One-time cloud setup, run by the owner in a private terminal: python -m scripts.deploy.setup_cloud

Asks for the secrets with hidden input, prepares the database, and stores the secrets as production variables of the
Vercel project this folder is linked to. Nothing secret is printed or written to a file. Safe to repeat.
"""
import json
import shutil
import subprocess
import sys
from getpass import getpass
from urllib.parse import urlsplit

from scripts import libpq  # noqa: F401  (must come before psycopg)

from scripts.migration import apply_migrations, export_sqlite, import_postgres, verify_migration
from scripts.migration.backup_sources import backup
from scripts.migration.common import ROOT

PROJECT_REF = "feocfauwwjgbugbqakhi"


def check_database_url(url):
    """The problem with a pasted connection string, or None."""
    if "[" in url or "]" in url:  # also what urlsplit refuses to parse
        return "Replace [YOUR-PASSWORD], brackets included, with the database password."
    parts = urlsplit(url)
    if parts.scheme not in ("postgresql", "postgres"):
        return "It must start with postgresql://"
    if not parts.password:
        return "The database password is missing."
    if PROJECT_REF not in f"{parts.username}{parts.hostname}":
        return f"It is not the connection string of project {PROJECT_REF}."
    if not (parts.hostname or "").endswith("pooler.supabase.com"):
        return "Use the pooler connection string; the direct one is IPv6 only."
    return None


def ask(prompt, problem):
    while True:
        value = getpass(prompt).strip()
        wrong = problem(value)
        if wrong is None:
            return value
        print(wrong)


def store(name, value):
    vercel = shutil.which("vercel") or sys.exit("The Vercel CLI is not installed.")
    done = subprocess.run([vercel, "env", "add", name, "production", "--sensitive", "--force", "--cwd", str(ROOT)],
                          input=value, text=True, capture_output=True)
    print(f"{name}: {'stored' if done.returncode == 0 else 'FAILED ' + done.stderr.replace(value, '***')[-300:]}")
    return done.returncode == 0


def main():
    url = ask("Transaction pooler string (hidden): ", check_database_url)
    secret = ask("Supabase secret key sb_secret_... (hidden): ",
                 lambda v: None if v.startswith("sb_secret_") else "It must start with sb_secret_")
    gemini = getpass("Gemini API key, or Enter to skip (hidden): ").strip()
    print("Migrations:", ", ".join(apply_migrations.apply(url)) or "nothing to apply")
    content = json.loads(export_sqlite.export(backup()).read_text(encoding="utf-8"))
    report = import_postgres.load(url, content)
    print("Rows inserted:", sum(t["inserted"] for t in report["tables"]), "rejected:", len(report["rejected"]))
    passed = verify_migration.verify(url, content, "hosted Supabase project (Mumbai)")
    print("Verification:", "PASS" if passed else "FAIL, see docs/migration/DATABASE_MIGRATION_REPORT.md")
    values = {"DATABASE_URL": url, "SUPABASE_SECRET_KEY": secret, **({"GEMINI_API_KEY": gemini} if gemini else {})}
    if not all([store(name, value) for name, value in values.items()]) or not passed:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
