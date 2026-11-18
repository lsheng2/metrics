import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('entry', [
    'workbench_serve_entry', 'publication_serve_entry', 'serve_signal_entry',
    'serve_stream_entry', 'serve_failure_entry', 'runtime_recovery_entry',
])
def test_serve_fixture_preludes_do_not_register_cleanup_before_capture(entry):
    script = """
import json, runpy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ai_host.tests import serve_test_entry
def at_bootstrap(**kwargs):
    from ai_host.exit_inventory import install_exit_capture
    capture = install_exit_capture()
    print(json.dumps({
        'preexisting_callbacks': capture.preexisting_callbacks,
        'preexisting_thread_callbacks': len(capture.preexisting_thread_callbacks),
    }))
    return 0
serve_test_entry.main = at_bootstrap
runpy.run_path(str(Path(sys.argv[1]) / 'ai_host/tests' / (sys.argv[2] + '.py')), run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(ROOT), entry],
        capture_output=True, text=True, timeout=12,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'preexisting_callbacks': 0, 'preexisting_thread_callbacks': 0,
    }


def probe(body, *args):
    script = """
import sys
sys.path.insert(0, sys.argv[1])
from ai_host.exit_inventory import install_exit_capture, collect_exit_inventory as inspect_exit
install_exit_capture()
def collect_exit_inventory():
    inventory = inspect_exit()
    inventory.cleanup_callbacks()
    inventory.cleanup_finalizers()
    return inventory.report, inventory.errors
""" + body
    return subprocess.run(
        [sys.executable, '-I', '-c', script, str(ROOT), *map(str, args)],
        capture_output=True, text=True, timeout=12,
    )


def test_inventory_rejects_unknown_callback_without_running_it():
    result = probe("""
import atexit, json
calls = []
def unknown():
    calls.append(True)
atexit.register(unknown)
report, errors = collect_exit_inventory()
assert calls == []
print(json.dumps({'report': report, 'errors': errors}))
""")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert 'unknown_atexit_callback' in data['errors']
    assert any(row['callback'] == '__main__.unknown' for row in data['report']['atexit'])


def test_inventory_explicitly_removes_owned_temporary_directories(tmp_path):
    result = probe("""
import json, logging, tempfile
from pathlib import Path
temporary = tempfile.TemporaryDirectory(dir=sys.argv[2])
path = Path(temporary.name)
(path / 'owned.txt').write_text('synthetic')
report, errors = collect_exit_inventory()
assert not path.exists()
print(json.dumps({'report': report, 'errors': errors}))
""", tmp_path)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['errors'] == []
    assert data['report']['event'] == 'serve_exit_inventory'
    assert any(row['callback'] == 'tempfile.TemporaryDirectory._cleanup'
               and row['cleanup'] == 'completed' for row in data['report']['finalizers'])


@pytest.mark.parametrize('resource', ['thread', 'finalizer', 'handler'])
def test_inventory_refuses_unknown_live_resource_ownership(resource):
    result = probe("""
import json, logging, threading, weakref
stop = threading.Event()
thread = None
class Resource:
    pass
owner = Resource()
if sys.argv[2] == 'thread':
    thread = threading.Thread(target=stop.wait, name='looks-owned-but-is-not')
    thread.start()
elif sys.argv[2] == 'finalizer':
    finalizer = weakref.finalize(owner, lambda: None)
else:
    class UnknownHandler(logging.Handler):
        def emit(self, record):
            pass
    handler = UnknownHandler()
    logging.getLogger().addHandler(handler)
try:
    report, errors = collect_exit_inventory()
    print(json.dumps({'report': report, 'errors': errors}))
finally:
    stop.set()
    if thread:
        thread.join(1)
""", resource)
    assert result.returncode == 0, result.stderr
    expected = {
        'thread': 'unresolved_thread',
        'finalizer': 'unknown_finalizer',
        'handler': 'unknown_log_handler',
    }[resource]
    assert expected in json.loads(result.stdout)['errors']


def test_callback_module_name_spoofing_does_not_grant_cleanup_authority():
    result = probe("""
import atexit, json, logging
def forged():
    raise AssertionError('forged callback executed')
forged.__module__ = 'logging'
forged.__qualname__ = 'shutdown'
atexit.register(forged)
report, errors = collect_exit_inventory()
atexit.unregister(forged)
print(json.dumps({'report': report, 'errors': errors}))
""")
    assert result.returncode == 0, result.stderr
    assert 'unknown_atexit_callback' in json.loads(result.stdout)['errors']


def test_inventory_reports_a_live_child_without_killing_or_adopting_it():
    result = probe("""
import json, subprocess
child = subprocess.Popen(
    [sys.executable, '-I', '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE,
)
try:
    report, errors = collect_exit_inventory()
    assert child.poll() is None
    assert any(row['pid'] == child.pid for row in report['children'])
    print(json.dumps({'report': report, 'errors': errors}))
finally:
    child.stdin.close()
    child.wait(timeout=3)
""")
    assert result.returncode == 0, result.stderr
    assert 'unresolved_child' in json.loads(result.stdout)['errors']


def test_serve_manage_entry_captures_callbacks_before_importing_django(tmp_path):
    script = """
import runpy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
class StopBeforeDjango:
    def find_spec(self, fullname, *args):
        if fullname == 'django':
            from ai_host.exit_inventory import get_exit_capture
            assert get_exit_capture() is not None
            print('captured-before-django', flush=True)
            raise RuntimeError('synthetic stop before Django')
sys.meta_path.insert(0, StopBeforeDjango())
sys.argv = ['manage.py', 'serve', '--port', '0']
try:
    runpy.run_path(str(Path(sys.path[0]) / 'manage.py'), run_name='__main__')
except RuntimeError:
    pass
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(ROOT)],
        capture_output=True, text=True, timeout=8,
    )
    assert result.returncode == 0, result.stderr
    assert 'captured-before-django' in result.stdout


@pytest.mark.parametrize('code', [0, 1, 3])
def test_every_ordinary_exit_records_inventory_and_performs_required_cleanup(tmp_path, code):
    result = probe("""
import tempfile
from pathlib import Path
from django.conf import settings
settings.configure(
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'project_management'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
)
import django
django.setup()
from ai_host.management.commands.serve import Command
temporary = tempfile.TemporaryDirectory(dir=sys.argv[2])
(Path(temporary.name) / 'owned.txt').write_text('synthetic')
Command()._exit(int(sys.argv[3]))
""", tmp_path, code)
    assert result.returncode == code, result.stdout + result.stderr
    assert not tuple(tmp_path.iterdir())
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    inventory = next(row for row in rows if row.get('event') == 'serve_exit_inventory')
    assert inventory['errors'] == []


def test_inventory_failure_overrides_startup_failure_and_does_not_wait_for_foreign_thread():
    result = probe("""
import threading
from django.conf import settings
settings.configure(
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'project_management'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
)
import django
django.setup()
from ai_host.management.commands.serve import Command
threading.Thread(target=lambda: threading.Event().wait(8), daemon=False).start()
Command()._exit(1)
""")
    assert result.returncode == 3, result.stderr
    assert 'unresolved_thread' in result.stdout
    assert 'serve cleanup failed.' in result.stdout


def test_late_registration_through_an_uncaptured_alias_cannot_pass():
    result = probe("""
import json
from ai_host.exit_inventory import get_exit_capture
get_exit_capture().original_register(lambda: None)
report, errors = collect_exit_inventory()
print(json.dumps({'report': report, 'errors': errors}))
""")
    assert result.returncode == 0, result.stderr
    assert 'exit_capture_incomplete' in json.loads(result.stdout)['errors']


def test_a_live_portalocker_resource_is_not_hidden_by_atexit_cleanup(tmp_path):
    result = probe("""
import json, portalocker
from pathlib import Path
lock = portalocker.TemporaryFileLock(str(Path(sys.argv[2]) / 'owned.lock'))
lock.acquire()
try:
    report, errors = collect_exit_inventory()
    assert lock.fh is not None
    print(json.dumps({'report': report, 'errors': errors}))
finally:
    lock.release()
""", tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'unreleased_file_lock' in json.loads(result.stdout)['errors']


def test_cleanup_failure_keeps_the_original_startup_diagnostic():
    result = probe("""
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'project_management'],
                   DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}})
import django
django.setup()
from ai_host.management.commands.serve import Command
Command()._exit(3, message='serve startup failed (start_timeout).')
""")
    assert result.returncode == 3
    assert result.stdout.index('serve startup failed (start_timeout).') < result.stdout.index('serve cleanup failed.')
