"""Load an export into PostgreSQL: python -m scripts.migration.import_postgres backups/<time>/export.json

Uses DATABASE_URL. One transaction: every row loads, or nothing does. Running it again adds nothing.
Rows the target refuses are listed and stop the load, unless --allow-rejects is given.
"""
import argparse
import json
import os
from pathlib import Path

import psycopg

from .common import MAPPING, SUPERSEDED, target_row

_IDENTITIES = [("app.ecn_reviews", "rowid"), ("app.planning_runs", "rowid"), ("app.what_if_requests", "rowid"),
               ("app.approvals", "rowid"), ("app.action_items", "rowid"), ("app.audit_log", "seq")]


def load(url, content, allow_rejects=False):
    report = {"tables": [], "rejected": []}
    with psycopg.connect(url) as conn:
        for source, table, target, _ in MAPPING:
            rows = content.get(source, {}).get("rows", {}).get(table, [])
            inserted = 0
            for original in rows:
                row = target_row(source, table, original)
                sql = (f"INSERT INTO {target} ({', '.join(row)}) VALUES ({', '.join(['%s'] * len(row))}) "
                       "ON CONFLICT DO NOTHING")
                try:
                    with conn.transaction():
                        inserted += conn.execute(sql, list(row.values())).rowcount
                except (psycopg.IntegrityError, psycopg.DataError) as error:
                    report["rejected"].append({"table": f"{source}.{table}", "row": original,
                                               "reason": str(error.diag.message_primary)})
            report["tables"].append({"source": f"{source}.{table}", "target": target, "source_rows": len(rows),
                                     "inserted": inserted})
        for source, table, why in SUPERSEDED:
            for row in content.get(source, {}).get("rows", {}).get(table, []):
                report["rejected"].append({"table": f"{source}.{table}", "row": row, "reason": why})
        for table, column in _IDENTITIES:
            conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                         f"greatest((SELECT coalesce(max({column}), 0) FROM {table}), 1), "
                         f"(SELECT count(*) > 0 FROM {table}))")
        if report["rejected"] and not allow_rejects:
            conn.rollback()
            report["rolled_back"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("--allow-rejects", action="store_true")
    args = parser.parse_args()
    outcome = load(os.environ["DATABASE_URL"], json.loads(args.export.read_text(encoding="utf-8")), args.allow_rejects)
    (args.export.parent / "import_report.json").write_text(json.dumps(outcome, indent=1), encoding="utf-8")
    for line in outcome["tables"]:
        print(f"{line['source']:28s} -> {line['target']:26s} {line['source_rows']:5d} rows, {line['inserted']:5d} inserted")
    for line in outcome["rejected"]:
        print("REJECTED", line["table"], line["reason"])
    raise SystemExit(1 if outcome.get("rolled_back") else 0)
