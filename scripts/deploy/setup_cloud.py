"""One-time cloud setup, run by the owner: python -m scripts.deploy.setup_cloud

Asks for the secrets in a window with masked fields, prepares the database, and stores the secrets as production variables of the
Vercel project this folder is linked to. Nothing secret is printed or written to a file. Safe to repeat.
"""
import json
import shutil
import subprocess
import sys
import tkinter
from urllib.parse import quote

from scripts import libpq  # noqa: F401  (must come before psycopg)
import psycopg

from scripts.migration import apply_migrations, export_sqlite, import_postgres, verify_migration
from scripts.migration.backup_sources import backup
from scripts.migration.common import ROOT

PROJECT_REF = "feocfauwwjgbugbqakhi"
POOLER = "aws-0-ap-south-1.pooler.supabase.com:6543"  # transaction pooler, Mumbai


def database_url(password):
    return f"postgresql://postgres.{PROJECT_REF}:{quote(password, safe='')}@{POOLER}/postgres?sslmode=require"


def problem(password, secret):
    """What is wrong with the two required answers, or None. Tries the password on the database."""
    if not password:
        return "Enter the database password."
    if not secret.startswith("sb_secret_"):
        return "The secret key must start with sb_secret_"
    try:
        psycopg.connect(database_url(password), connect_timeout=15).close()
    except psycopg.Error as error:
        return "The database password is wrong." if "password authentication" in str(error) else "The database cannot be reached."
    return None


def ask():
    """(password, secret key, Gemini key), or exit when the window is closed."""
    window = tkinter.Tk()
    window.title("ChangeWise cloud setup")
    window.attributes("-topmost", True)
    fields = []
    for label in ("Database password", "Supabase secret key (sb_secret_...)", "Gemini API key (optional)"):
        tkinter.Label(window, text=label, anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        entry = tkinter.Entry(window, show="*", width=60)
        entry.pack(padx=20)
        fields.append(entry)
    message = tkinter.Label(window, fg="#b00020")
    message.pack(pady=8)
    answers = []

    def submit(_event=None):
        values = [field.get().strip() for field in fields]
        message.config(text="Checking...")
        window.update()
        wrong = problem(values[0], values[1])
        if wrong:
            message.config(text=wrong)
        else:
            answers.extend(values)
            window.destroy()

    tkinter.Button(window, text="Continue", command=submit).pack(pady=(0, 16))
    window.bind("<Return>", submit)
    fields[0].focus_force()
    window.mainloop()
    return answers or sys.exit("Closed without answers.")


def store(name, value):
    vercel = shutil.which("vercel") or sys.exit("The Vercel CLI is not installed.")
    done = subprocess.run([vercel, "env", "add", name, "production", "--sensitive", "--force", "--cwd", str(ROOT)],
                          input=value, text=True, capture_output=True)
    print(f"{name}: {'stored' if done.returncode == 0 else 'FAILED ' + done.stderr.replace(value, '***')[-300:]}")
    return done.returncode == 0


def main():
    password, secret, gemini = ask()
    url = database_url(password)
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
