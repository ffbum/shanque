"""Run existing business tests in isolated schemas of a disposable PG database."""
import hashlib
import os
import sys
import unittest
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.conninfo import make_conninfo
import workspace
url = os.environ["SHANQUE_TEST_DATABASE_URL"]
original = workspace.create_app
schemas = {}
run_id = uuid.uuid4().hex[:12]
def create_app(config=None, **kwargs):
    config = dict(config or {})
    key = config.get("DATABASE") or kwargs.get("instance_path") or str(uuid.uuid4())
    name = "verify_" + run_id + "_" + hashlib.sha256(str(key).encode()).hexdigest()[:12]
    if name not in schemas:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{name}"')
        schemas[name] = True
    config["DATABASE_SCHEMA"] = name
    config["DATABASE_TYPE"] = os.environ.get("SHANQUE_TEST_DB_TYPE", "postgresql")
    config["DATABASE_URL"] = make_conninfo(url, options=f"-csearch_path={name},public")
    return original(config, **kwargs)
workspace.create_app = create_app
try:
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
finally:
    with psycopg.connect(url, autocommit=True) as conn:
        for name in schemas:
            conn.execute(f'DROP SCHEMA "{name}" CASCADE')
sys.exit(not result.wasSuccessful())
