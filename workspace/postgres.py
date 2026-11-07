"""PostgreSQL / KingbaseES PG mode backend for the workspace SQL interface."""
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict
from psycopg import sql as pgsql
from psycopg.pq import TransactionStatus


class Result:
    def __init__(self, cursor, inserted=False):
        self.cursor = cursor
        self.lastrowid = cursor.fetchone()["id"] if inserted else None
        self.rowcount = cursor.rowcount

    def __iter__(self):
        return iter(self.cursor)

    def fetchone(self):
        return self.cursor.fetchone()


class Connection:
    def __init__(self, url, *, kingbase=False, schema="public"):
        defaults = {} if "connect_timeout" in conninfo_to_dict(url) else {"connect_timeout": 10}
        self.raw = psycopg.connect(url, autocommit=True, row_factory=dict_row, **defaults)
        try:
            if kingbase:
                mode = self.raw.execute("SHOW database_mode").fetchone()["database_mode"]
                if mode.lower() != "pg":
                    raise ValueError("KingbaseES must use PG compatibility mode (database_mode=pg)")
            # Only this application's schema is searched; never fall back to public tables.
            quoted_schema = '"' + schema.replace('"', '""') + '"'
            self.raw.execute("SELECT set_config('search_path', %s, false)", (quoted_schema,))
            if self.raw.execute("SELECT current_schema() AS name").fetchone()["name"] != schema:
                raise ValueError("Database schema does not exist or the account lacks USAGE permission")
        except Exception:
            self.raw.close()
            raise

    @property
    def in_transaction(self):
        return self.raw.info.transaction_status != TransactionStatus.IDLE

    def execute(self, sql, args=()):
        if sql == "BEGIN IMMEDIATE":
            self.raw.execute("BEGIN")
            # Preserve the application's serialized read-check-write semantics.
            return self.raw.execute("SELECT pg_advisory_xact_lock(73508126)")
        ignore = "INSERT OR IGNORE" in sql.upper()
        sql = re.sub(r"INSERT OR IGNORE", "INSERT", sql, flags=re.I)
        # The application's SQL uses placeholders only outside string literals.
        parts = re.split(r"('(?:''|[^'])*')", sql)
        sql = "".join(part.replace("?", "%s") if i % 2 == 0 else part.replace("%", "%%")
                      for i, part in enumerate(parts))
        # Match SQLite NOCASE behavior for account and team lookups.
        sql = re.sub(r"\b(login|name)=%s", r"lower(\1)=lower(%s)", sql) if (
            sql.lstrip().upper().startswith("SELECT") and re.search(r"FROM (person|team)\b", sql)
        ) else sql
        if ignore:
            sql += " ON CONFLICT DO NOTHING"
        inserted = bool(re.match(r"INSERT INTO (person|project|milestone|task|team)\s*\(", sql, re.I))
        if inserted:
            sql += " RETURNING id"
        return Result(self.raw.execute(sql, args or None), inserted)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.rollback() if kind else self.commit()

    def initialize(self):
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        schema = schema.replace("id INTEGER PRIMARY KEY", "id SERIAL PRIMARY KEY")
        schema = schema.replace(" UNIQUE COLLATE NOCASE", "")
        with self:
            self.execute("BEGIN IMMEDIATE")
            self.raw.execute(schema)
            for column in ("start_date", "end_date", "project_type"):
                self.raw.execute(f"ALTER TABLE project ADD COLUMN IF NOT EXISTS {column} TEXT")
            self.raw.execute("ALTER TABLE task ADD COLUMN IF NOT EXISTS start_date TEXT")
            constraints = self.raw.execute("""SELECT conname, pg_get_constraintdef(oid) AS definition
                FROM pg_constraint WHERE conrelid='project'::regclass AND contype='c'""").fetchall()
            for constraint in constraints:
                if "project_type" in constraint["definition"]:
                    self.raw.execute(pgsql.SQL("ALTER TABLE project DROP CONSTRAINT {}").format(
                        pgsql.Identifier(constraint["conname"])))
            self.raw.execute("ALTER TABLE project ADD CONSTRAINT project_type_check "
                             "CHECK(project_type IN ('科研','工程','固投','自研','预研'))")
            self.raw.execute("CREATE UNIQUE INDEX IF NOT EXISTS person_login_nocase ON person(lower(login))")
            self.raw.execute("CREATE UNIQUE INDEX IF NOT EXISTS team_name_nocase ON team(lower(name))")
            self.raw.execute("ALTER TABLE task ADD COLUMN IF NOT EXISTS revision TEXT NOT NULL DEFAULT ''")
            self.raw.execute("UPDATE task SET revision=md5(random()::text || clock_timestamp()::text) WHERE revision=''")
            self.raw.execute("""
                CREATE OR REPLACE FUNCTION shanque_task_revision() RETURNS trigger AS $$
                BEGIN
                    NEW.revision := md5(random()::text || clock_timestamp()::text);
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                DROP TRIGGER IF EXISTS task_revision ON task;
                CREATE TRIGGER task_revision BEFORE INSERT OR UPDATE OF
                    name,due,start_date,milestone_id,is_key,status,note,done_at,done_by
                    ON task FOR EACH ROW EXECUTE PROCEDURE shanque_task_revision();
            """)
