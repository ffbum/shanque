from unittest.mock import patch
from workspace import create_app
from tests.fixtures import seed_demo

def create_test_app(*args, **kwargs):
    with patch('workspace.seed.seed', seed_demo):
        return create_app(*args, **kwargs)
