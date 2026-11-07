"""Resolve database selection for the app and migration command."""
import os
import re


def database_config(environ=None, overrides=None):
    env = os.environ if environ is None else environ
    overrides = overrides or {}
    url = overrides.get("DATABASE_URL", env.get("SHANQUE_DATABASE_URL", "")) or ""
    kind = overrides.get("DATABASE_TYPE", env.get("SHANQUE_DB_TYPE", "")).strip().lower()
    kind = kind or ("postgresql" if url else "sqlite")
    if kind == "postgres":
        kind = "postgresql"
    if kind not in ("sqlite", "postgresql", "kingbase"):
        raise ValueError("SHANQUE_DB_TYPE must be sqlite, postgresql or kingbase")
    if kind == "sqlite":
        if url:
            raise ValueError("Remove SHANQUE_DATABASE_URL when selecting sqlite")
        return {"DATABASE_TYPE": kind, "DATABASE_URL": None}
    schema = overrides.get("DATABASE_SCHEMA", env.get("SHANQUE_DB_SCHEMA")) or "public"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", schema):
        raise ValueError("SHANQUE_DB_SCHEMA must be a simple identifier of at most 63 characters")
    if url:
        return {"DATABASE_TYPE": kind, "DATABASE_URL": url, "DATABASE_SCHEMA": schema}
    required = ("SHANQUE_DB_HOST", "SHANQUE_DB_NAME", "SHANQUE_DB_USER")
    for name in required:
        if not env.get(name, "").strip():
            raise ValueError(f"{name} is required for an external database")
    try:
        port = int(env.get("SHANQUE_DB_PORT") or (54321 if kind == "kingbase" else 5432))
        timeout = int(env.get("SHANQUE_DB_CONNECT_TIMEOUT") or 10)
    except ValueError:
        raise ValueError("Database port and connection timeout must be integers") from None
    if not 1 <= port <= 65535 or timeout <= 0:
        raise ValueError("Database port must be 1..65535 and connection timeout must be positive")
    sslmode = env.get("SHANQUE_DB_SSLMODE") or "prefer"
    if sslmode not in ("disable", "allow", "prefer", "require", "verify-ca", "verify-full"):
        raise ValueError("Invalid SHANQUE_DB_SSLMODE")
    from psycopg.conninfo import make_conninfo
    url = make_conninfo(host=env["SHANQUE_DB_HOST"].strip(), port=port,
                        dbname=env["SHANQUE_DB_NAME"].strip(), user=env["SHANQUE_DB_USER"].strip(),
                        password=env.get("SHANQUE_DB_PASSWORD", ""), sslmode=sslmode,
                        connect_timeout=timeout)
    return {"DATABASE_TYPE": kind, "DATABASE_URL": url, "DATABASE_SCHEMA": schema}
