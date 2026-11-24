"""Copy both SQLite databases to backups/<time>/ with checksums: python -m scripts.migration.backup_sources"""
import os
import sqlite3
import stat
from datetime import datetime, timezone

from .common import BACKUPS, SOURCES, connect, sha256


def backup():
    folder = BACKUPS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    lines = []
    for name, path in SOURCES.items():
        if not path.exists():
            print(f"{name}: no database at {path}")
            continue
        target = folder / f"{name}.db"
        source, copy = connect(path), sqlite3.connect(target)
        source.backup(copy)  # consistent even while the application is running
        copy.close()
        source.close()
        os.chmod(target, stat.S_IREAD)
        lines.append(f"{sha256(target)}  {target.name}")
    (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return folder


if __name__ == "__main__":
    print(backup())
