import unittest
from unittest.mock import patch
from psycopg.conninfo import conninfo_to_dict
from workspace.database_config import database_config
from workspace.postgres import Connection


class DatabaseConfiguration(unittest.TestCase):
    def fields(self, **extra):
        return {"SHANQUE_DB_TYPE": "kingbase", "SHANQUE_DB_HOST": "db.internal",
                "SHANQUE_DB_NAME": "shanque", "SHANQUE_DB_USER": "app", **extra}

    def test_default_and_explicit_sqlite_do_not_connect_externally(self):
        for env in ({}, {"SHANQUE_DB_TYPE": "sqlite", "SHANQUE_DB_HOST": "ignored"}):
            self.assertEqual(database_config(env), {"DATABASE_TYPE": "sqlite", "DATABASE_URL": None})

    def test_kingbase_password_and_database_names_round_trip(self):
        env = self.fields(SHANQUE_DB_PASSWORD="a' \\ $ # @ : / 密码", SHANQUE_DB_NAME="project space")
        settings = database_config(env)
        params = conninfo_to_dict(settings["DATABASE_URL"])
        self.assertEqual(settings["DATABASE_TYPE"], "kingbase")
        self.assertEqual(params["port"], "54321")
        self.assertEqual(params["password"], env["SHANQUE_DB_PASSWORD"])
        self.assertEqual(params["dbname"], "project space")

    def test_postgresql_defaults_and_explicit_options(self):
        env = self.fields(SHANQUE_DB_TYPE="postgresql")
        self.assertEqual(conninfo_to_dict(database_config(env)["DATABASE_URL"])["port"], "5432")
        env.update(SHANQUE_DB_PORT="6543", SHANQUE_DB_CONNECT_TIMEOUT="7", SHANQUE_DB_SSLMODE="require")
        params = conninfo_to_dict(database_config(env)["DATABASE_URL"])
        self.assertEqual((params["port"], params["connect_timeout"], params["sslmode"]), ("6543", "7", "require"))

    def test_legacy_url_and_explicit_app_override(self):
        url = "host=old dbname=project user=app"
        self.assertEqual(database_config({"SHANQUE_DATABASE_URL": url})["DATABASE_URL"], url)
        result = database_config(self.fields(), {"DATABASE_TYPE": "sqlite", "DATABASE_URL": None})
        self.assertIsNone(result["DATABASE_URL"])
        result = database_config({}, {"DATABASE_URL": url})
        self.assertEqual(result["DATABASE_TYPE"], "postgresql")

    def test_invalid_settings_fail_without_exposing_password(self):
        for env in ({"SHANQUE_DB_TYPE": "mysql"}, {"SHANQUE_DB_TYPE": "kingbase"},
                    self.fields(SHANQUE_DB_PORT="oops"), self.fields(SHANQUE_DB_PORT="65536"),
                    self.fields(SHANQUE_DB_CONNECT_TIMEOUT="0"), self.fields(SHANQUE_DB_SSLMODE="invalid"),
                    {"SHANQUE_DB_TYPE": "sqlite", "SHANQUE_DATABASE_URL": "host=db"}):
            env["SHANQUE_DB_PASSWORD"] = "secret-not-in-error"
            with self.assertRaises(ValueError) as error:
                database_config(env)
            self.assertNotIn("secret-not-in-error", str(error.exception))

    @patch("workspace.postgres.psycopg.connect")
    def test_kingbase_non_pg_mode_is_rejected_before_schema_changes(self, connect):
        raw = connect.return_value
        raw.execute.return_value.fetchone.return_value = {"database_mode": "oracle"}
        with self.assertRaisesRegex(ValueError, "PG compatibility"):
            Connection("host=test", kingbase=True)
        raw.execute.assert_called_once_with("SHOW database_mode")
        raw.close.assert_called_once()

    @patch("workspace.postgres.psycopg.connect")
    def test_postgresql_does_not_query_kingbase_setting(self, connect):
        connect.return_value.execute.return_value.fetchone.return_value = {"name": "private_app"}
        Connection("host=test", schema="private_app")
        queries = [call.args[0] for call in connect.return_value.execute.call_args_list]
        self.assertNotIn("SHOW database_mode", queries)
        connect.return_value.execute.assert_any_call("SELECT set_config('search_path', %s, false)", ('"private_app"',))

    def test_schema_selection_and_identifier_validation(self):
        self.assertEqual(database_config(self.fields(SHANQUE_DB_SCHEMA="shanque"))["DATABASE_SCHEMA"], "shanque")
        self.assertEqual(database_config(self.fields())["DATABASE_SCHEMA"], "public")
        for schema in ("app,public", "app;DROP TABLE person", "a" * 64):
            with self.assertRaises(ValueError):
                database_config(self.fields(SHANQUE_DB_SCHEMA=schema))

    @patch("workspace.postgres.psycopg.connect")
    def test_missing_schema_fails_without_creating_business_tables(self, connect):
        connect.return_value.execute.return_value.fetchone.return_value = {"name": None}
        with self.assertRaisesRegex(ValueError, "schema does not exist"):
            Connection("host=test", schema="missing")
        connect.return_value.close.assert_called_once()
        self.assertEqual(connect.return_value.execute.call_count, 2)
