"""Copy a consistent SQLite backup into an empty PostgreSQL/KingbaseES database."""
import argparse
import sqlite3
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root if (root / "workspace").exists() else Path("/app")))
from psycopg import sql
from workspace.postgres import Connection
from workspace.database_config import database_config

TABLES = ("person", "project", "membership", "milestone", "task", "assignment", "team", "team_member", "project_team")

def migrate(source, backup, url, *, kingbase=False, schema="public"):
    if backup.exists():
        raise ValueError("Backup destination already exists")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(backup) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
    source_db = sqlite3.connect(backup)
    source_db.row_factory = sqlite3.Row
    db = Connection(url, kingbase=kingbase, schema=schema)
    try:
        db.initialize()
        with db:
            db.execute("BEGIN IMMEDIATE")
            for table in TABLES:
                if db.raw.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table))).fetchone():
                    raise ValueError("Target must be empty: " + table)
            for table in TABLES:
                records = source_db.execute(f'SELECT * FROM "{table}"').fetchall()
                for row in records:
                    columns = list(row.keys())
                    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
                        sql.SQL(",").join(sql.Placeholder() for _ in columns))
                    db.raw.execute(query, tuple(row))
                    if table == "task" and "revision" in columns:
                        db.raw.execute("UPDATE task SET revision=%s WHERE id=%s", (row["revision"], row["id"]))
                actual = db.raw.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))).fetchall()
                expected = [dict(row) for row in records]
                normalize = lambda items: sorted((tuple(sorted(item.items())) for item in items), key=repr)
                if normalize(actual) != normalize(expected):
                    raise ValueError("Row verification failed: " + table)
                if table in ("person", "project", "milestone", "task", "team"):
                    maximum = max((r["id"] for r in records), default=0)
                    db.raw.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),%s,%s)",
                                   (table, max(maximum, 1), maximum > 0))
                print(f"{table}: {len(records)} rows verified")
    finally:
        source_db.close()
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    settings = database_config()
    if not settings["DATABASE_URL"]:
        parser.error("Select kingbase or postgresql as the target database")
    migrate(args.source, args.backup, settings["DATABASE_URL"],
            kingbase=settings["DATABASE_TYPE"] == "kingbase", schema=settings["DATABASE_SCHEMA"])
