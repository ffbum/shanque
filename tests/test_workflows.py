import re
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from tests.support import create_test_app as create_app
from workspace.db import first
from workspace.gantt import build_chart
from workspace.model import summary, today


class Workflows(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.app = create_app(
            {"TESTING": True, "DATABASE": str(Path(directory.name) / "test.sqlite3")}
        )
        self.client = self.app.test_client()
        self.login("manager")

    def login(self, username):
        self.client = self.app.test_client()
        self.client.get("/login")
        response = self.post("/login", login=username, password="Demo12345!")
        self.assertEqual(response.status_code, 302, response.data)

    def post(self, path, **fields):
        self.client.get("/login")
        with self.client.session_transaction() as s:
            fields["csrf"] = s["csrf"]
        task_status = re.fullmatch(r"/projects/\d+/tasks/(\d+)/status", path)
        if task_status:
            fields.setdefault("revision", self.getrow("SELECT revision FROM task WHERE id=?", task_status[1])["revision"])
        return self.client.post(path, data=fields)

    def getrow(self, sql, *values):
        with self.app.app_context():
            return first(sql, values)

    def test_login_form_survives_background_requests(self):
        client = self.app.test_client()
        page = client.get("/login").get_data(as_text=True)
        token = re.search(r'name="csrf" value="([^"]+)"', page)[1]
        client.get("/favicon.ico")
        client.get("/")
        response = client.post(
            "/login",
            data={"login": "manager", "password": "Demo12345!", "csrf": token},
            follow_redirects=True,
        )
        self.assertIn("项目台账", response.get_data(as_text=True))

    def accepted(self, path, **fields):
        res = self.post(path, **fields)
        self.assertEqual(res.status_code, 302, res.data.decode())
        return res.location

    def test_force_completion_only_updates_unfinished_tasks_on_selected_node(self):
        path = "/projects/1"
        target = path + "/milestones/2/confirm"
        planned = self.getrow("SELECT planned FROM milestone WHERE id=2")["planned"]
        self.accepted(path + "/tasks/new", name="会签", start_date=planned, milestone_id="2", assignees=["4"])
        new_task = self.getrow("SELECT * FROM task WHERE name='会签'")
        node = self.getrow("SELECT planned FROM milestone WHERE id=2")
        self.assertEqual(new_task["due"], node["planned"])
        previous = self.getrow("SELECT * FROM task WHERE id=2")
        self.login("member")
        self.assertEqual(self.post(target, force="1").status_code, 403)
        self.login("lead")
        self.accepted(target, force="1")
        mark = self.getrow("SELECT actor,achieved FROM milestone WHERE id=2")
        self.assertEqual(mark["actor"], 3)
        for tid in (3, new_task["id"]):
            t = self.getrow("SELECT * FROM task WHERE id=?", tid)
            self.assertEqual((t["status"], t["done_by"], t["done_at"]),
                             ("已完成", mark["actor"], mark["achieved"]))
        self.assertEqual(self.getrow("SELECT * FROM task WHERE id=2"), previous)
        for tid in (4, 5):
            self.assertEqual(self.getrow("SELECT status FROM task WHERE id=?", tid)["status"], "未开始")
        self.login("manager")
        self.accepted(target, force="1")
        self.assertEqual(self.getrow("SELECT actor,achieved FROM milestone WHERE id=2"), mark)

    def test_gantt_includes_unscheduled_projects_and_respects_visibility(self):
        path = self.accepted("/projects/new", project_type="工程", name="年度专项", leads=["5"])
        self.assertIn("年度专项", self.client.get("/gantt").get_data(as_text=True))
        self.accepted(path + "/milestones/new", name="专项验收", planned="2031-12-01")
        mid = self.getrow("SELECT id FROM milestone WHERE name='专项验收'")["id"]
        self.accepted(path + "/tasks/new", name="跨年复核", due="2032-01-06",
                      milestone_id=str(mid), assignees=["5"])
        self.login("director")
        page = self.client.get("/gantt").get_data(as_text=True)
        self.assertIn("专项验收", page)
        self.assertIn("2031-12-01", page)
        self.assertIn("跨年复核", page)
        self.assertIn('datetime="2032-01-06"', page)
        self.login("member")
        page = self.client.get("/gantt").get_data(as_text=True)
        self.assertNotIn("年度专项", page)
        self.assertNotIn("专项验收", page)
        self.assertNotIn("2031-12-01", page)
        self.assertNotIn("跨年复核", page)
        self.assertNotIn("2032-01-06", page)

    def test_project_stages_and_parallel_tasks(self):
        path = self.accepted("/projects/new", project_type="工程", name="排期验证", leads=["3"],
                             start_date="2030-01-01", end_date="2030-02-01")
        for planned in ("2030-01-10", "2030-01-20"):
            self.accepted(path + "/milestones/new", name=planned, planned=planned)
        pid = int(path.split("/")[-1])
        mid = self.getrow("SELECT max(id) AS id FROM milestone WHERE project_id=?", pid)["id"]
        for due in ("2030-01-16", "2030-01-18"):
            self.accepted(path + "/tasks/new", name=due, start_date="2030-01-05",
                          due=due, milestone_id=str(mid), assignees=["4"])
        with self.app.app_context():
            p = summary(first("SELECT * FROM project WHERE id=?", (pid,)))
            build_chart([p], today())
        a, b = p["milestones"]
        self.assertEqual(p["left"], a["stage_x"])
        self.assertEqual(b["stage_x"], a["plan_x"])
        self.assertEqual(p["tasks"][0]["start_x"], p["tasks"][1]["start_x"])
        self.assertLess(p["tasks"][0]["start_x"], b["stage_x"])
        # Extending the project by years must not compress the original stages.
        stage_width = b["plan_x"] - a["plan_x"]
        p["end_date"] = "2035-02-01"
        chart = build_chart([p], today())
        self.assertEqual(b["plan_x"] - a["plan_x"], stage_width)
        self.assertEqual(stage_width, 10 * chart["day_width"])
        self.assertEqual(self.post(path+"/tasks/new", name="逆序",start_date="2030-01-05",
                                   due="2030-01-01",assignees=["4"]).status_code,400)
        self.assertIn(today().isoformat(), self.client.get(path+"/tasks/new").get_data(as_text=True))

    def test_entire_project(self):
        path = self.accepted(
            "/projects/new", project_type="工程", name="验收项目", description="", leads=["3", "5"]
        )
        pid = int(path.split("/")[-1])
        for label in ("自动节点", "人工节点"):
            self.accepted(path + "/milestones/new", name=label, planned="2026-12-12")
        mid = self.getrow(
            "SELECT id FROM milestone WHERE project_id=? ORDER BY id", (pid)
        )["id"]
        self.login("lead")
        self.accepted(
            path + "/tasks/new",
            name="共同签收",
            due="2026-12-12",
            milestone_id=str(mid),
            assignees=["4", "6"],
        )
        self.accepted(
            path + "/tasks/new",
            name="整理资料",
            due="2026-12-14",
            milestone_id=str(mid),
            assignees=["4"],
        )
        tid = self.getrow("SELECT id FROM task WHERE name=?", "共同签收")["id"]
        plain = tid + 1
        self.assertEqual(
            self.getrow("SELECT COUNT(*) AS n FROM membership WHERE project_id=?", pid)[
                "n"
            ],
            4,
        )
        self.assertEqual(
            self.post(
                path + f"/milestones/{mid}/edit", name="越权", planned="2026-11-10"
            ).status_code,
            403,
        )
        self.login("manager")
        self.accepted(
            path + f"/milestones/{mid}/edit",
            name="自动节点",
            planned="2026-12-12",
            forecast="2026-12-14",
            key=str(tid),
        )
        self.assertEqual(
            self.post(path + f"/milestones/{mid}/confirm").status_code, 409
        )
        self.assertEqual(self.post(path + "/close").status_code, 409)
        self.login("member")
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(
            self.post(
                path + f"/tasks/{tid}/status", status="受阻", note=""
            ).status_code,
            400,
        )
        self.accepted(path + f"/tasks/{tid}/status", status="受阻", note="等回执")
        self.accepted(path + f"/tasks/{tid}/status", status="已完成")
        self.login("xu")
        self.accepted(path + f"/tasks/{tid}/status", status="已完成")
        self.assertEqual(
            self.getrow("SELECT done_by FROM task WHERE id=?", tid)["done_by"], 4
        )
        self.assertEqual(
            self.getrow("SELECT actor FROM milestone WHERE id=?", mid)["actor"], 4
        )
        self.assertEqual(
            self.post(path + f"/tasks/{plain}/status", status="已完成").status_code, 403
        )
        self.login("lead")
        self.accepted(path + f"/milestones/{mid + 1}/confirm")
        self.accepted(path + "/close")
        self.login("member")
        self.accepted(path + f"/tasks/{plain}/status", status="已完成")
        with self.app.app_context():
            p = summary(first("SELECT * FROM project WHERE id=?", (pid,)))
        self.assertEqual(
            (p["reached"], p["done"], len(p["tasks"]), p["state"]), (2, 2, 2, "已结项")
        )

    def test_visibility_and_lead_scope(self):
        path = self.accepted("/projects/new", project_type="工程", name="独立项目", leads=["5"])
        self.login("lead")
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get("/projects/1/edit").status_code, 200)
        self.login("manager")
        self.accepted(path + "/members", members=["3"])
        self.login("lead")
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get(path + "/tasks/new").status_code, 403)
        self.login("manager")
        self.accepted(path + "/edit", project_type="工程", name="独立项目", leads=["3", "5"])
        self.login("lead")
        self.assertEqual(self.client.get(path + "/tasks/new").status_code, 200)
        self.login("manager")
        self.accepted(path + "/edit", project_type="工程", name="独立项目", leads=["5"])
        self.login("lead")
        self.assertEqual(self.client.get(path + "/tasks/new").status_code, 403)
        self.login("director")
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(
            self.post(path + "/progress", progress="越权").status_code, 403
        )
        self.assertEqual(self.client.get("/accounts").status_code, 403)

    def test_dates_progress_and_rollback(self):
        with self.app.app_context():
            p = summary(first("SELECT * FROM project WHERE id=1"))
        self.assertEqual(p["overdue"][0]["name"], "方案评审")
        self.assertEqual(p["upcoming"][0]["name"], "现场联调")
        self.accepted("/projects/1/progress", progress="联调完成")
        self.assertIn("联调完成", self.client.get("/").get_data(as_text=True))
        self.assertEqual(
            self.post("/projects/new", project_type="工程", name="应回滚", leads=["9999"]).status_code, 400
        )
        self.assertIsNone(self.getrow("SELECT id FROM project WHERE name=?", "应回滚"))
        self.assertEqual(self.client.post("/projects/1/close").status_code, 400)

    def test_excel_and_account_lifecycle(self):
        def upload(data):
            book = Workbook()
            book.active.append(["账号", "姓名", "角色", "初始密码"])
            for line in data:
                book.active.append(line)
            buf = BytesIO()
            book.save(buf)
            buf.seek(0)
            return self.post("/accounts/import", file=(buf, "人员.xlsx"))

        entry = ["newperson", "新增成员", "成员", "Demo12345!"]
        self.assertEqual(upload([entry, entry]).status_code, 409)
        self.assertIsNone(self.getrow("SELECT id FROM person WHERE login=?", entry[0]))
        self.assertEqual(upload([entry]).status_code, 302)
        uid = self.getrow("SELECT id FROM person WHERE login=?", entry[0])["id"]
        self.login("newperson")
        old = self.client
        self.login("manager")
        self.accepted(
            "/accounts/save",
            id=str(uid),
            name="新增成员",
            role="成员",
            active="0",
            password="Reset12345!",
        )
        self.assertTrue(old.get("/").location.endswith("/login"))

    def test_node_deletion_preserves_tasks(self):
        self.accepted("/projects/1/milestones/2/edit", delete="1")
        t = self.getrow("SELECT milestone_id,is_key FROM task WHERE id=3")
        self.assertEqual(t, {"milestone_id": None, "is_key": 0})
        self.assertEqual(
            self.getrow("SELECT COUNT(*) AS n FROM task WHERE project_id=1")["n"], 5
        )


if __name__ == "__main__":
    unittest.main()
