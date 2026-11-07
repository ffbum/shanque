"""The Pro client uses the same authenticated routes with a JSON representation."""
import unittest
from tempfile import TemporaryDirectory

from tests.support import create_test_app as create_app


class FrontendAPI(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app({"TESTING": True, "FRONTEND_ENABLED": True}, instance_path=self.directory.name)
        self.client = self.app.test_client()
        self.headers = {"Accept": "application/json"}
        self.login("manager")

    def get(self, path):
        response = self.client.get(path, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json

    def post(self, path, **values):
        context = self.get("/api/session")
        values.setdefault("csrf", context["csrf"])
        values.setdefault("team_context", str(context["team"]["id"]) if context["team"] else "")
        return self.client.post(path, data=values, headers=self.headers)

    def login(self, login):
        self.client = self.app.test_client()
        self.assertEqual(self.post("/login", login=login, password="Demo12345!").status_code, 200)

    def test_admin_password_reset_preserves_account_and_revokes_sessions(self):
        from workspace.db import first
        from werkzeug.security import check_password_hash
        with self.app.app_context():
            before = first("SELECT * FROM person WHERE login='member'")
        self.login('member')
        old_client = self.client
        self.assertEqual(self.post('/accounts/password', id=before['id'], password='NewPassword123!').status_code, 403)
        self.login('manager')
        self.assertEqual(self.post('/accounts/password', id=before['id'], password='short').status_code, 400)
        self.assertEqual(self.post('/accounts/password', id=before['id'], password='NewPassword123!').status_code, 200)
        with self.app.app_context():
            after = first("SELECT * FROM person WHERE id=?", (before['id'],))
        self.assertTrue(check_password_hash(after['password'], 'NewPassword123!'))
        for key in before:
            if key not in ('password', 'version'):
                self.assertEqual(before[key], after[key])
        self.assertEqual(after['version'], before['version'] + 1)
        self.assertIsNone(old_client.get('/api/session', headers=self.headers).json['user'])

    def test_admin_grant_revoke_and_last_admin(self):
        from workspace.db import first
        with self.app.app_context():
            manager = first("SELECT id FROM person WHERE login='manager'")['id']
            member = first("SELECT id FROM person WHERE login='member'")['id']
        self.assertEqual(self.post('/accounts/admin', id=manager, admin=0).status_code, 409)
        self.login('member')
        self.assertEqual(self.post('/accounts/admin', id=member, admin=1).status_code, 403)
        self.login('manager')
        self.assertEqual(self.post('/accounts/admin', id=member, admin=1).status_code, 200)
        self.login('member')
        self.assertTrue(self.get('/api/session')['user']['admin'])
        self.assertEqual(self.post('/accounts/admin', id=manager, admin=0).status_code, 200)
        self.assertEqual(self.post('/accounts/admin', id=member, admin=0).status_code, 409)
        self.assertEqual(self.post('/accounts/admin', id=manager, admin=1).status_code, 200)
        self.assertEqual(self.post('/accounts/admin', id=member, admin=0).status_code, 200)
        self.assertEqual(self.client.get('/accounts', headers=self.headers).status_code, 403)

    def test_all_pages_share_session_and_serializable_dates(self):
        for path in ("/", "/gantt", "/todo", "/projects/1", "/projects/new", "/projects/1/edit",
                     "/projects/1/tasks/new", "/projects/1/milestones/new", "/team/members", "/teams", "/teams/1", "/accounts", "/password"):
            body = self.get(path)
            self.assertEqual(body["context"]["user"]["login"], "manager")
            self.assertTrue(body["context"]["csrf"])
            self.assertNotIn("password", body["context"]["user"])
        gantt = self.get("/gantt")["data"]
        self.assertRegex(gantt["chart"]["start"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(gantt["chart"]["day_width"], 24)
        with self.client.get('/') as response:
            self.assertIn('id="root"', response.get_data(as_text=True))

    def test_project_types_roundtrip_validation_and_legacy_upgrade(self):
        from workspace.db import connection, initialize, rows
        with self.app.app_context():
            db = connection()
            db.execute('ALTER TABLE project DROP COLUMN project_type')
            db.commit()
            before = rows('SELECT * FROM project ORDER BY id')
            initialize()
            initialize()
            after = rows('SELECT * FROM project ORDER BY id')
            self.assertEqual(before, [{k:v for k,v in p.items() if k != 'project_type'} for p in after])
            self.assertTrue(all(p['project_type'] is None for p in after))
        # A ledger that already used the original four types also upgrades in place.
        with self.app.app_context():
            db = connection()
            db.execute('ALTER TABLE project DROP COLUMN project_type')
            db.execute("ALTER TABLE project ADD COLUMN project_type TEXT CHECK(project_type IN ('科研','工程','固投','自研'))")
            db.execute("UPDATE project SET project_type='科研' WHERE id=2")
            db.commit()
            initialize()
            initialize()
            self.assertEqual(rows('SELECT project_type FROM project WHERE id=2')[0]['project_type'], '科研')
            self.assertEqual(rows('PRAGMA foreign_key_check'), [])
        for kind in ('科研', '工程', '固投', '自研', '预研'):
            response = self.post('/projects/new', name=kind+'项目', project_type=kind, leads=[3])
            self.assertEqual(response.status_code, 200, response.json)
            path = response.json['redirect']
            self.assertEqual(self.get(path)['data']['p']['project_type'], kind)
            self.assertEqual(self.post(path+'/edit', name='改名', leads=[3]).status_code, 400)
            self.assertEqual(self.post(path+'/edit', name='改名', leads=[3], project_type=kind).status_code, 200)
            self.assertEqual(self.get(path)['data']['p']['project_type'], kind)
        self.assertEqual(self.post('/projects/1/edit', name='禁止', leads=[3], project_type='其他').status_code, 400)
        self.assertEqual(self.post('/projects/1/edit', name='禁止', leads=[3], project_type='').status_code, 400)
        self.assertIsNone(self.get('/projects/1')['data']['p']['project_type'])
        self.login('director')
        self.assertEqual(self.post('/projects/1/edit', name='禁止', leads=[3], project_type='科研').status_code, 403)

    def test_json_writes_conflicts_and_force_completion(self):
        self.assertEqual(self.post('/projects/new', name='未选类型', leads=[3]).status_code, 400)
        result = self.post('/projects/new', name='React验收', project_type='自研', leads=[3], start_date='2030-01-01', end_date='2030-12-31')
        self.assertEqual(result.status_code, 200)
        path = result.json['redirect']
        self.assertEqual(self.post(path+'/milestones/new', name='交付', planned='2030-06-01').status_code, 200)
        mid = self.get(path)['data']['p']['milestones'][0]['id']
        self.assertEqual(self.post(path+'/tasks/new', name='并行执行', start_date='2030-01-02', due='2030-06-01', milestone_id=mid, assignees=[3,4]).status_code, 200)
        task = self.get(path)['data']['p']['tasks'][0]
        status = path+f'/tasks/{task["id"]}/status'
        values = dict(status='进行中', note='联调', revision=task['revision'])
        self.assertEqual(self.post(status, **values).status_code, 200)
        self.assertEqual(self.post(status, **values).status_code, 409)
        self.assertEqual(self.post(path+f'/milestones/{mid}/confirm', force=1).status_code, 200)
        project = self.get(path)['data']['p']
        self.assertEqual(project['tasks'][0]['status'], '已完成')
        self.assertTrue(project['milestones'][0]['achieved'])
        self.assertEqual(self.post(path+'/close').status_code, 200)

    def test_json_auth_and_team_permissions(self):
        self.assertEqual(self.post('/projects/1/progress', progress='bad', csrf='invalid').status_code, 400)
        self.assertEqual(self.post('/teams/save', name='新组', supervisor=1).status_code, 200)
        tid = self.get('/teams')['data']['teams'][-1]['id']
        self.assertEqual(self.post('/teams/switch', team_id=tid, next='work.gantt').json['redirect'], '/gantt')
        self.assertEqual(self.get('/gantt')['data']['projects'], [])
        self.assertEqual(self.post('/projects/1/progress', progress='bad', team_context='1').status_code, 409)
        self.assertEqual(self.client.get('/projects/1',headers=self.headers).status_code, 403)
        self.login('director')
        self.assertEqual(self.post('/projects/1/progress', progress='bad').status_code, 403)
        self.assertEqual(self.post('/logout').json['redirect'], '/login')
        self.assertEqual(self.client.get('/',headers=self.headers).status_code, 401)


if __name__ == '__main__':
    unittest.main()
