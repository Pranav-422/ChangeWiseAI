"""Compare an export with PostgreSQL, value by value, and write docs/migration/DATABASE_MIGRATION_REPORT.md.

    python -m scripts.migration.verify_migration backups/<time>/export.json
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from backend.app.core import database
from member3.services import audit_service

from . import capture_baseline
from .common import MAPPING, ROOT, target_row

REPORT = ROOT / "docs" / "migration" / "DATABASE_MIGRATION_REPORT.md"
_JSON = {"extraction", "fields", "validation", "dataset", "config", "result", "context", "explanation", "parameters",
         "plan", "action", "payload", "result_json", "rejection_reasons_json"}


def _same(column, expected, actual):
    if column in _JSON and isinstance(expected, str):
        return json.loads(expected) == (json.loads(actual) if isinstance(actual, str) else actual)
    return expected == actual


def compare(url, content):
    results = []
    with psycopg.connect(url, row_factory=dict_row) as conn:
        database._configure(conn)
        conn.execute("SET timezone TO 'UTC'")
        for source, table, target, key in MAPPING:
            rows = [target_row(source, table, r) for r in content.get(source, {}).get("rows", {}).get(table, [])]
            stored = {tuple(r[k] for k in key): r for r in conn.execute(f"SELECT * FROM {target}").fetchall()}
            missing, different = [], []
            for row in rows:
                found = stored.get(tuple(row[k] for k in key))
                if found is None:
                    missing.append([row[k] for k in key])
                else:
                    different += [f"{[row[k] for k in key]}.{c}: {str(v)[:40]} -> {str(found[c])[:40]}"
                                  for c, v in row.items() if not _same(c, v, found[c])]
            results.append({"source": f"{source}.{table}", "target": target, "source_rows": len(rows),
                            "target_rows": len(stored), "missing": missing, "different": different})
        foreign_keys = conn.execute("SELECT count(*) AS n, count(*) FILTER (WHERE NOT convalidated) AS bad FROM "
                                    "pg_constraint WHERE contype = 'f' AND connamespace IN "
                                    "('core'::regnamespace, 'app'::regnamespace)").fetchone()
        unprotected = [r["relname"] for r in conn.execute(
            "SELECT relname FROM pg_class WHERE relkind = 'r' AND NOT relrowsecurity AND relnamespace IN "
            "('core'::regnamespace, 'app'::regnamespace)")]
        version = conn.execute("SELECT split_part(version(), ' ', 2) AS v").fetchone()["v"]
    return results, foreign_keys, unprotected, version


def write_report(results, foreign_keys, unprotected, version, chain, parity, where):
    ok = not any(r["missing"] or r["different"] for r in results) and not unprotected and chain is None \
        and not foreign_keys["bad"] and not any(parity.values())
    lines = ["# Database migration report", "",
             f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by "
             "`scripts/migration/verify_migration.py`.", "",
             f"* Target: PostgreSQL {version}, {where}.",
             f"* Result: **{'PASS' if ok else 'FAIL'}**", "",
             "| Source table | Target table | Source rows | Target rows | Missing | Values that differ |",
             "|---|---|---:|---:|---:|---:|"]
    lines += [f"| {r['source']} | {r['target']} | {r['source_rows']} | {r['target_rows']} | {len(r['missing'])} "
              f"| {len(r['different'])} |" for r in results]
    for r in results:
        lines += [f"* MISSING {r['target']} {m}" for m in r["missing"]]
        lines += [f"* DIFFERENT {r['target']} {d}" for d in r["different"]]
    lines += ["", f"* Foreign keys: {foreign_keys['n']} defined, {foreign_keys['bad']} not validated.",
              f"* Tables without Row Level Security: {', '.join(unprotected) or 'none'}.",
              f"* Audit chain: {'intact' if chain is None else f'broken at event {chain}'}.",
              "* Engine output on PostgreSQL data compared with the frozen baseline (every value of validation, BOM, "
              "simulation, exceptions, plans, ranking, robustness, baselines, replay):", ""]
    lines += [f"  * {name}: {'identical' if not found else f'{len(found)} differences'}" for name, found in parity.items()]
    lines += ["", "## Decisions", "",
              "* `plan_actions` (proposed by the engine) and `action_items` (approved tasks) stay separate; "
              "`action_items.plan_action_id` links them, and `action_status_history` records every status.",
              "* `app.audit_log` is the one live audit log. Member 1's audit rows go to `app.legacy_audit_events` "
              "with their original IDs. `app.audit_events` shows both.",
              "* Member 1's proposed `action_tracker` is superseded by `action_items`; it is not created. "
              "Its rows, if any, are reported as rejected by the import.",
              "* Snapshots that are hashed or replayed use JSON, because JSONB would rewrite them. Other JSON uses JSONB.",
              "* Money is NUMERIC; flags are BOOLEAN; IDs are unchanged. The engines still receive floats and 0/1 flags.",
              "* `audit_log.created_at` stays TEXT because it is inside the hash. `recorded_at` is the server's own time.",
              "* The SQLite files are not modified. Backups are read-only copies with SHA-256 sums in `backups/` "
              "(not committed)."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return ok


def verify(url, content, where):
    results, foreign_keys, unprotected, version = compare(url, content)
    database.open_pool(url)
    try:
        chain = audit_service.verify_chain()
        parity = capture_baseline.check("backend.app.integrations.member1_postgres")
    finally:
        database.close_pool()
    return write_report(results, foreign_keys, unprotected, version, chain, parity, where)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("--where", default="target database", help="how the report names the target")
    args = parser.parse_args()
    passed = verify(os.environ["DATABASE_URL"], json.loads(args.export.read_text(encoding="utf-8")), args.where)
    print(REPORT.read_text(encoding="utf-8"))
    raise SystemExit(0 if passed else 1)
