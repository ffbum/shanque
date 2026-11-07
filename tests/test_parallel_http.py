"""Exercise simultaneous browser sessions against a real Waitress listener and temporary SQLite file."""
import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener

from waitress import create_server

from tests.support import create_test_app as create_app
from workspace.db import connection, execute, first, rows


def hidden(page, name):
    return re.search(fr'name="{name}" value="([^"]+)"', page)[1]


class Browser:
    def __init__(self, base, login):
        self.base = base
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        _, page = self.request("/login")
        code, page = self.request("/login", dict(login=login, password="Demo12345!", csrf=hidden(page, "csrf")))
        assert code == 200 and 'name="password"' not in page
        self.csrf = hidden(page, "csrf")

    def request(self, path, fields=None):
        data = urlencode(fields).encode() if fields is not None else None
        try:
            response = self.opener.open(self.base + path, data=data, timeout=30)
        except HTTPError as err:
            response = err
        with response:
            return response.status, response.read().decode()


class ParallelHttp(unittest.TestCase):
    def test_read_write_and_stale_forms(self):
        with TemporaryDirectory() as directory:
            app = create_app({"FRONTEND_ENABLED": False}, instance_path=str(Path(directory).resolve()))
            with app.app_context(), connection():
                for i in range(12):
                    execute("""INSERT INTO person(login,name,role,password)
                               SELECT ?,?,'主管',password FROM person WHERE login='manager'""",
                            (f"user{i}", f"测试{i}"))
                    execute("INSERT INTO team_member(team_id,person_id,role) "
                            "SELECT 1,id,'主管' FROM person WHERE login=?", (f"user{i}",))
                tasks = [execute("INSERT INTO task(project_id,name,due,start_date) VALUES(1,?,?,?)",
                                 (f"task{i}", "2030-02-01", "2030-01-01")).lastrowid for i in range(12)]

            server = create_server(app, host="127.0.0.1", port=0, threads=8)
            thread = Thread(target=server.run, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.effective_port}"
                browsers = [Browser(base, f"user{i}") for i in range(12)]

                def parallel(count, action):
                    gate = Barrier(count)
                    def run(i):
                        gate.wait(timeout=20)
                        return action(i)
                    with ThreadPoolExecutor(count) as pool:
                        return list(pool.map(run, range(count)))

                def path(i):
                    return f"/projects/1/tasks/{tasks[i]}/edit"

                def form(i, revision, name):
                    return dict(csrf=browsers[i].csrf, revision=revision, name=name,
                                start_date="2030-01-01", due="2030-02-01", assignees=4)

                for cycle in range(4):
                    pages = parallel(12, lambda i: browsers[i].request(path(i)))
                    self.assertTrue(all(code == 200 for code, _ in pages))
                    def mixed(i):
                        if (i + cycle) % 2:
                            return browsers[i].request("/projects/1")
                        token = hidden(pages[i][1], "revision")
                        return browsers[i].request(path(i), form(i, token, f"saved-{cycle}-{i}"))
                    results = parallel(12, mixed)
                    self.assertTrue(all(code == 200 for code, _ in results))
                    with app.app_context():
                        for i in range(12):
                            if (i + cycle) % 2 == 0:
                                self.assertEqual(first("SELECT name FROM task WHERE id=?", (tasks[i],))["name"],
                                                 f"saved-{cycle}-{i}")

                tokens = [hidden(browsers[i].request(path(0))[1], "revision") for i in range(2)]
                self.assertEqual(*tokens)
                outcomes = parallel(2, lambda i: browsers[i].request(path(0), form(i, tokens[i], f"winner-{i}")))
                codes = [code for code, _ in outcomes]
                self.assertCountEqual(codes, [200, 409])
                winner = codes.index(200)
                loser = 1 - winner
                stale = dict(csrf=browsers[loser].csrf, revision=tokens[loser])
                self.assertEqual(browsers[loser].request(path(0), dict(stale, delete=1))[0], 409)
                status_path = path(0).replace("/edit", "/status")
                self.assertEqual(browsers[loser].request(status_path, dict(stale, status="已完成"))[0], 409)
                with app.app_context():
                    self.assertEqual(first("SELECT name,status FROM task WHERE id=?", (tasks[0],)),
                                     dict(name=f"winner-{winner}", status="未开始"))
                    self.assertEqual(rows("PRAGMA foreign_key_check"), [])
                latest = hidden(browsers[loser].request(path(0))[1], "revision")
                self.assertEqual(browsers[loser].request(path(0), form(loser, latest, "reconciled"))[0], 200)
                with app.app_context():
                    self.assertEqual(first("SELECT name FROM task WHERE id=?", (tasks[0],))["name"], "reconciled")
            finally:
                server.close()
                thread.join(timeout=3)
