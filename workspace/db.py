import sqlite3
from pathlib import Path

from flask import current_app, g


def connection():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def execute(sql, args=()):
    return connection().execute(sql, args)


def rows(sql, args=()):
    return [dict(row) for row in execute(sql, args)]


def first(sql, args=()):
    row = execute(sql, args).fetchone()
    return dict(row) if row else None


def initialize():
    connection().execute("PRAGMA journal_mode=WAL")
    connection().executescript(
        Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    )
    # Upgrade the existing local ledger in place, including packaged installations.
    with connection():
        execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in rows("PRAGMA table_info(project)")}
        for column in ("start_date", "end_date"):
            if column not in columns:
                execute(f"ALTER TABLE project ADD COLUMN {column} TEXT")
        if "project_type" not in columns:
            execute("ALTER TABLE project ADD COLUMN project_type TEXT "
                    "CHECK(project_type IN ('科研','工程','固投','自研','预研'))")
        elif "'预研'" not in first("SELECT sql FROM sqlite_master WHERE type='table' AND name='project'")["sql"]:
            # Expand the original four-value constraint without touching other project fields or relationships.
            execute("ALTER TABLE project RENAME COLUMN project_type TO project_type_previous")
            execute("ALTER TABLE project ADD COLUMN project_type TEXT "
                    "CHECK(project_type IN ('科研','工程','固投','自研','预研'))")
            execute("UPDATE project SET project_type=project_type_previous")
            execute("ALTER TABLE project DROP COLUMN project_type_previous")
        task_columns = {row["name"] for row in rows("PRAGMA table_info(task)")}
        if "start_date" not in task_columns:
            execute("ALTER TABLE task ADD COLUMN start_date TEXT")
        if "revision" not in task_columns:
            execute("ALTER TABLE task ADD COLUMN revision TEXT NOT NULL DEFAULT ''")
            execute("UPDATE task SET revision=lower(hex(randomblob(16)))")
        # Fresh tokens also distinguish a newly inserted task that reuses a deleted ID.
        for event, label in (("INSERT", "insert"), (
            "UPDATE OF name,due,start_date,milestone_id,is_key,status,note,done_at,done_by", "update"
        )):
            execute(f"""CREATE TRIGGER IF NOT EXISTS task_revision_{label} AFTER {event} ON task
                        BEGIN UPDATE task SET revision=lower(hex(randomblob(16))) WHERE id=NEW.id; END""")



def initialize_teams():
    # Run after seed so both existing ledgers and new installs have a team.
    with connection():
        execute("BEGIN IMMEDIATE")
        if first("SELECT id FROM team LIMIT 1"):
            return
        tid = execute("INSERT INTO team(name) VALUES('默认团队')").lastrowid
        execute("INSERT INTO team_member SELECT ?,id,role FROM person", (tid,))
        execute("INSERT INTO project_team SELECT id,? FROM project", (tid,))


def close(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
