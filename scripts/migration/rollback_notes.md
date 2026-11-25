# Rollback

The migration only reads SQLite, so rolling back never loses source data.

1. **Application.** Stop using the Vercel and Render services. The Streamlit application still runs on SQLite:
   `streamlit run member3/application/app.py`. Nothing in it depends on PostgreSQL.
2. **Failed import.** `import_postgres` is one transaction. A failure leaves the database as it was.
3. **Wrong data after a successful import.** On a disposable project, drop schemas `core` and `app` and apply
   the migrations again. On a project with real decisions, restore the Supabase backup taken before the import;
   the audit and planning-run tables refuse UPDATE and DELETE on purpose.
4. **SQLite file damaged.** Copy `backups/<time>/member1.db` or `member3.db` back after checking `SHA256SUMS`.

Records written to PostgreSQL after the switch are not copied back to SQLite.
