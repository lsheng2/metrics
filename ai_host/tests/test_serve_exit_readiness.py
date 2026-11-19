"""The bounded exit path must not first discover its implementation on disk."""
import json

import pytest

from ai_host.tests.test_serve_exit_inventory import probe


@pytest.mark.parametrize("code", [0, 1, 3])
def test_command_exit_is_ready_before_filesystem_module_discovery_is_unavailable(code):
    result = probe("""
from django.conf import settings
settings.configure(
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'project_management'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
)
import django
django.setup()
from ai_host.management.commands.serve import Command
class RefuseLateExitImport:
    def find_spec(self, fullname, *args):
        if fullname == 'ai_host.serve_exit':
            raise RuntimeError('exit implementation first loaded during bounded shutdown')
sys.meta_path.insert(0, RefuseLateExitImport())
Command()._exit(int(sys.argv[2]))
""", code)
    assert result.returncode == code, result.stdout + result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    cleanup = next(row for row in records if row.get("event") == "serve_exit_cleanup")
    assert cleanup["errors"] == []
