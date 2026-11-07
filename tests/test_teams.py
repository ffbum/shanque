import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.support import create_test_app as create_app
from workspace.db import connection, execute, first, rows


class TeamWorkflows(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app({"TESTING": True}, instance_path=str(Path(self.directory.name).resolve()))
        self.manager = self.login("manager")

    def login(self, name):
        client = self.app.test_client()
        client.get("/login")
        self.assertEqual(self.post(client, "/login", login=name, password="Demo12345!").status_code, 302)
        client.get("/")
        return client

    def post(self, client, path, **data):
        with client.session_transaction() as session:
            data.setdefault("csrf", session["csrf"])
        return client.post(path, data=data)

    def row(self, query, *args):
        with self.app.app_context():
            return first(query, args)

    def accepted(self, client, path, **data):
        response = self.post(client, path, **data)
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True))
        return response

    def make_team(self):
        self.accepted(self.manager, "/teams/save", name="工程组", supervisor=5)
        return self.row("SELECT id FROM team WHERE name='工程组'")["id"]

    def add(self, tid, uid, role="成员"):
        self.accepted(self.manager, f"/teams/{tid}/members", person_id=uid, role=role)

    def switch(self, client, tid, target="work.overview"):
        self.accepted(client, "/teams/switch", team_id=tid, next=target)

    def create_project(self, client, name="工程专属"):
        response = self.accepted(client, "/projects/new", project_type="工程", name=name, leads=[5])
        return int(response.location.rsplit("/", 1)[1])

    def task_status(self, client, pid, tid, **data):
        revision = self.row("SELECT revision FROM task WHERE id=?", tid)["revision"]
        return self.post(client, f"/projects/{pid}/tasks/{tid}/status", revision=revision, **data)

    def test_roles_and_project_visibility_are_team_scoped(self):
        tid = self.make_team()
        self.add(tid, 1, "总监")
        supervisor = self.login("lin")
        self.switch(supervisor, tid)
        pid = self.create_project(supervisor)
        self.assertNotIn("工程专属", self.manager.get("/").get_data(as_text=True))
        self.assertEqual(self.manager.get(f"/projects/{pid}").status_code, 403)
        self.assertEqual(self.post(self.manager, f"/projects/{pid}/progress", progress="越权").status_code, 403)
        self.switch(self.manager, tid, "work.gantt")
        page = self.manager.get("/gantt").get_data(as_text=True)
        self.assertIn("工程专属", page)
        self.assertNotIn("智能检测产线升级", page)
        self.assertEqual(self.post(self.manager, "/projects/new", name="越权", leads=[5]).status_code, 403)
        self.assertEqual(self.manager.get(f"/projects/{pid}/milestones/new").status_code, 403)
        self.accepted(self.manager, f"/teams/{tid}/projects", project_id=1)
        self.assertIn("智能检测产线升级", self.manager.get("/").get_data(as_text=True))
        self.assertEqual(self.post(self.manager, "/projects/1/progress", progress="越权").status_code, 403)
        self.switch(self.manager, 1)
        self.accepted(self.manager, "/projects/1/progress", progress="跨团队同步")
        self.switch(self.manager, tid)
        self.assertIn("跨团队同步", self.manager.get("/").get_data(as_text=True))
        self.assertEqual(self.row("SELECT count(*) n FROM project")["n"], 5)

    def test_supervisor_roster_and_role_administration(self):
        tid = self.make_team()
        supervisor = self.login("lin")
        self.switch(supervisor, tid)
        self.accepted(supervisor, f"/teams/{tid}/members", person_id=6)
        page = supervisor.get("/team/members").get_data(as_text=True)
        self.assertIn("许明", page)
        self.assertNotIn("<td>director</td>", page)
        self.assertEqual(supervisor.get("/accounts").status_code, 403)
        self.assertEqual(supervisor.get("/teams").status_code, 403)
        self.assertEqual(self.post(supervisor, f"/teams/{tid}/members", person_id=6, role="主管").status_code, 403)
        self.assertEqual(self.post(supervisor, f"/teams/{tid}/members", person_id=4, role="总监").status_code, 403)
        self.assertEqual(self.post(supervisor, "/teams/1/members", person_id=6, remove=1).status_code, 403)
        self.accepted(supervisor, f"/teams/{tid}/members", person_id=6, remove=1)
        self.add(tid, 6, "总监")
        self.assertEqual(self.post(supervisor, f"/teams/{tid}/members", person_id=6, remove=1).status_code, 403)
        self.assertIsNotNone(self.row("SELECT * FROM team_member WHERE team_id=? AND person_id=6", tid))

    def test_personal_tasks_are_global_deduplicated_and_authorized(self):
        tid = self.make_team()
        self.add(tid, 4)
        supervisor = self.login("lin")
        self.switch(supervisor, tid)
        pid = self.create_project(supervisor)
        self.accepted(supervisor, f"/projects/{pid}/tasks/new", name="工程任务", start_date="2030-01-01",
                      due="2030-02-01", assignees=[4])
        task = self.row("SELECT id FROM task WHERE name='工程任务'")["id"]
        self.accepted(self.manager, f"/teams/{tid}/projects", project_id=1)
        member = self.login("member")
        page = member.get("/todo").get_data(as_text=True)
        self.assertEqual(page.count("工程任务</b>"), 1)
        self.assertEqual(page.count('id="status-3"'), 1)
        self.assertEqual(self.task_status(member, pid, task, source="todo", status="进行中").status_code, 302)
        stale = self.row("SELECT revision FROM task WHERE id=?", task)["revision"]
        self.assertEqual(self.task_status(member, pid, task, source="todo", status="进行中", note="已更新").status_code, 302)
        conflict = self.post(member, f"/projects/{pid}/tasks/{task}/status",
                             source="todo", revision=stale, status="已完成")
        self.assertEqual(conflict.status_code, 409)
        self.assertIn(f"/projects/{pid}?team={tid}", conflict.get_data(as_text=True))
        self.assertEqual(self.task_status(member, pid, task, status="已完成").status_code, 403)
        self.switch(member, tid)
        self.add(tid, 4, "总监")
        page = member.get("/todo").get_data(as_text=True)
        self.assertNotIn(f'id="status-{task}"', page)
        self.assertIn('id="status-3"', page)
        self.assertEqual(self.task_status(member, pid, task, source="todo", status="已完成").status_code, 403)
        self.assertEqual(self.task_status(member, 1, 3, source="todo", status="进行中").status_code, 302)
        self.assertEqual(self.task_status(member, 1, 4, source="todo", status="进行中").status_code, 403)
        self.assertEqual(member.get("/projects/1?team=999").status_code, 403)

    def test_user_account_role_never_grants_team_permissions(self):
        self.accepted(self.manager, "/accounts/save", login="newchief", name="新账户", role="主管", password="Demo12345!")
        client = self.login("newchief")
        uid = self.row("SELECT id FROM person WHERE login='newchief'")["id"]
        self.assertEqual(client.get("/projects/1").status_code, 403)
        self.assertNotIn("智能检测产线升级", client.get("/").get_data(as_text=True))
        self.assertEqual(self.post(client, "/teams/switch", team_id=1).status_code, 403)
        self.add(1, uid, "成员")
        self.assertEqual(client.get("/projects/1").status_code, 403)
        self.assertEqual(self.post(client, "/projects/new", name="越权", leads=[3]).status_code, 403)
        self.add(1, uid, "主管")
        self.assertEqual(client.get("/projects/1").status_code, 200)
        self.add(1, uid, "总监")
        self.assertEqual(self.post(client, "/projects/1/progress", progress="越权").status_code, 403)

    def test_removals_preserve_assigned_work_and_team_context(self):
        tid = self.make_team()
        self.add(tid, 1, "主管")
        self.accepted(self.manager, f"/teams/{tid}/projects", project_id=1)
        # Removing the only team that contains the assigned people must roll back.
        self.assertEqual(self.post(self.manager, "/teams/1/projects", project_id=1, remove=1).status_code, 409)
        self.assertIsNotNone(self.row("SELECT * FROM project_team WHERE project_id=1 AND team_id=1"))
        self.assertEqual(self.post(self.manager, "/teams/1/members", person_id=3, remove=1).status_code, 409)
        self.accepted(self.manager, f"/teams/{tid}/projects", project_id=1, remove=1)
        self.assertEqual(self.post(self.manager, "/teams/1/projects", project_id=1, remove=1).status_code, 409)
        self.switch(self.manager, tid)
        self.assertEqual(self.post(self.manager, "/projects/new", team_context="1", name="旧页面", leads=[5]).status_code, 409)
        self.assertIsNone(self.row("SELECT id FROM project WHERE name='旧页面'"))

    def test_legacy_data_migration_is_complete_and_idempotent(self):
        with self.app.app_context(), connection():
            snapshot = {name: rows(f"SELECT * FROM {name} ORDER BY 1,2")
                        for name in ("person", "project", "membership", "milestone", "task", "assignment")}
            execute("DROP TABLE project_team")
            execute("DROP TABLE team_member")
            execute("DROP TABLE team")
        self.app = create_app({"TESTING": True}, instance_path=self.directory.name)
        with self.app.app_context(), connection():
            for table, contents in snapshot.items():
                self.assertEqual(rows(f"SELECT * FROM {table} ORDER BY 1,2"), contents)
            self.assertEqual(rows("SELECT person_id,role FROM team_member ORDER BY person_id"),
                             [dict(person_id=u["id"],role=u["role"]) for u in snapshot["person"]])
            self.assertEqual(len(rows("SELECT * FROM project_team")), len(snapshot["project"]))
            execute("DELETE FROM team_member WHERE person_id=6")
        self.app = create_app({"TESTING": True}, instance_path=self.directory.name)
        self.assertIsNone(self.row("SELECT * FROM team_member WHERE person_id=6"))
        with self.app.app_context():
            if not self.app.config.get("DATABASE_URL"):
                self.assertEqual(rows("PRAGMA foreign_key_check"), [])


if __name__ == "__main__":
    unittest.main()
