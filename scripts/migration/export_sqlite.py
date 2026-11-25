"""Every row of both SQLite databases as one JSON file: python -m scripts.migration.export_sqlite [folder]"""
import json
import sys
from pathlib import Path

from .backup_sources import backup
from .common import connect, sha256, tables


def export(folder):
    """Reads the backups in `folder`, so the export and the backup are the same moment."""
    content = {}
    for path in sorted(Path(folder).glob("*.db")):
        db = connect(path)
        content[path.stem] = {"sha256": sha256(path), "schema": {}, "rows": {}}
        for table in tables(db):
            content[path.stem]["schema"][table] = db.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?", [table]).fetchone()[0]
            content[path.stem]["rows"][table] = [dict(r) for r in db.execute(
                f"SELECT * FROM {table} ORDER BY 1" if path.stem == "member1"
                else f"SELECT rowid, * FROM {table} ORDER BY rowid")]
        db.close()
    target = Path(folder) / "export.json"
    target.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(export(sys.argv[1] if len(sys.argv) > 1 else backup()))
