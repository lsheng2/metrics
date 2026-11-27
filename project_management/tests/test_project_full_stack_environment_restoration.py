from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.validation.project_full_stack_support import base_environment


pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows environment contract')
ROOT = Path(__file__).resolve().parents[2]
PROBE = r'''
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])
from scripts.validation.project_full_stack_support import sanitized_process_environment

root, mode = Path(sys.argv[2]), sys.argv[3]
keys = ['GIT_CONFIG_VALUE_0', 'SYNTHETIC_EMPTY_ONE', 'SYNTHETIC_EMPTY_TWO',
        'SYNTHETIC_TEXT', 'SYNTHETIC_ABSENT', 'OPENAI_API_KEY', 'METRICS_JIRA_API_TOKEN']

def native_values():
    code = 'import os,json; print(json.dumps({key: os.environ.get(key) for key in ' + repr(keys) + '}))'
    completed = subprocess.run(
        [sys.executable, '-I', '-B', '-c', code],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(completed.stdout)

def git_config():
    completed = subprocess.run(
        ['git', 'config', '--get', 'test.nativeempty'],
        cwd=root, capture_output=True, text=True, timeout=10,
    )
    return {'returncode': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr}

class BodyFailure(Exception):
    pass

class FailedSetter:
    def __call__(self, key, value):
        ctypes.set_last_error(87)
        return False

before = native_values()
git_before = git_config()
original = dict(os.environ)
if mode == 'native-failure':
    ctypes.WinDLL = lambda *args, **kwargs: SimpleNamespace(SetEnvironmentVariableW=FailedSetter())
body_error = False
try:
    with sanitized_process_environment(root / 'scope'):
        inside = native_values()
        os.environ['SYNTHETIC_ABSENT'] = 'temporary'
        os.environ['SYNTHETIC_EMPTY_ONE'] = 'temporary'
        os.environ['SYNTHETIC_TEXT'] = 'temporary'
        if mode == 'body-failure':
            raise BodyFailure()
except BodyFailure:
    body_error = True
except OSError as error:
    print(json.dumps({'native_restore_error': error.winerror}))
    sys.exit(1)
print(json.dumps({
    'before': before, 'inside': inside, 'after': native_values(),
    'python_restored': dict(os.environ) == original, 'body_error': body_error,
    'git_before': git_before, 'git_after': git_config(),
}))
'''


def run_probe(tmp_path, mode):
    # Launch with an explicit block: Python assignment alone does not establish
    # a native empty value on the affected Windows interpreter.
    environment = base_environment(tmp_path / 'outer')
    environment.update(
        GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='test.nativeempty', GIT_CONFIG_VALUE_0='',
        SYNTHETIC_EMPTY_ONE='', SYNTHETIC_EMPTY_TWO='', SYNTHETIC_TEXT='retained',
        OPENAI_API_KEY='SYNTHETIC_MODEL', METRICS_JIRA_API_TOKEN='SYNTHETIC_PROVIDER',
    )
    return subprocess.run(
        [sys.executable, '-I', '-B', '-c', PROBE, str(ROOT), str(tmp_path), mode],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize('mode', ['normal', 'body-failure'])
def test_restores_native_empty_nonempty_and_absent_values_without_leaking_credentials(tmp_path, mode):
    completed = run_probe(tmp_path, mode)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    observed = json.loads(completed.stdout)
    expected = {
        'GIT_CONFIG_VALUE_0': '', 'SYNTHETIC_EMPTY_ONE': '', 'SYNTHETIC_EMPTY_TWO': '',
        'SYNTHETIC_TEXT': 'retained', 'SYNTHETIC_ABSENT': None,
        'OPENAI_API_KEY': 'SYNTHETIC_MODEL', 'METRICS_JIRA_API_TOKEN': 'SYNTHETIC_PROVIDER',
    }
    assert observed['before'] == expected
    assert observed['git_before']['returncode'] == 0, observed['git_before']
    assert observed['inside'] == {key: None for key in expected}
    assert observed['python_restored'] is True
    assert observed['body_error'] is (mode == 'body-failure')
    assert observed['after'] == expected
    assert observed['git_after']['returncode'] == 0, observed['git_after']
    assert observed['git_after']['stdout'].strip() == ''


def test_native_restoration_failure_is_not_silently_accepted(tmp_path):
    completed = run_probe(tmp_path, 'native-failure')
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {'native_restore_error': 87}
