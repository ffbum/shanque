import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from workspace import create_app
from workspace.db import first

class EmptyInstallation(unittest.TestCase):
    def test_fresh_server_has_no_projects_or_demo_accounts(self):
        with TemporaryDirectory() as directory:
            with patch('workspace.seed.getpass', side_effect=['FreshInstall123!', 'FreshInstall123!']):
                app = create_app({'TESTING': True}, instance_path=directory)
            with app.app_context():
                for table in ('project', 'task', 'milestone'):
                    self.assertEqual(first(f'SELECT COUNT(*) AS n FROM {table}')['n'], 0)
                self.assertEqual(first('SELECT COUNT(*) AS n FROM person')['n'], 1)
                self.assertEqual(first('SELECT login,admin FROM person'), {'login': 'manager', 'admin': 1})
            with patch('workspace.seed.getpass') as prompt:
                create_app({'TESTING': True}, instance_path=directory)
                prompt.assert_not_called()
