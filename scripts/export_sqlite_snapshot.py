"""Export a standalone SQLite snapshot and checksums for offline migration."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def export(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / "workspace.sqlite3"
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite snapshot integrity check failed")
            tables = ("person", "project", "membership", "milestone", "task", "assignment", "team", "team_member", "project_team")
            counts = {table: dst.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in tables}
    metadata = destination / "snapshot.json"
    metadata.write_text(json.dumps({"exported_at": datetime.now(timezone.utc).isoformat(), "rows": counts}, indent=2) + "\n", encoding="utf-8")
    checks = []
    for file in (target, metadata):
        with file.open("rb") as stream:
            checks.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {file.name}\n")
    (destination / "SHA256SUMS").write_text("".join(checks), encoding="utf-8", newline="\n")
    print("Snapshot exported:", destination.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export(args.source, args.destination)
