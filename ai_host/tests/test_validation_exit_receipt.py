import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('code', [0, 1, 3, 130])
def test_join_wrapper_records_actual_explicit_exit_instead_of_relying_on_finally(tmp_path, code):
    root = Path(__file__).resolve().parents[2]
    receipt = tmp_path / 'exit.json'
    script = """
import os, runpy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from django import core
from django.core import management
code = int(sys.argv[3])
management.execute_from_command_line = lambda argv: os._exit(code)
sys.argv = [
    'wrapper', '--qualify-launch-id', 'synthetic-launch',
    '--qualify-exit-file', sys.argv[2], 'serve',
]
runpy.run_path(str(Path(sys.path[0]) / 'scripts/validation/project_full_stack_app_entry.py'), run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(root), str(receipt), str(code)],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding='utf-8'))
    assert payload['exit_code'] == code
    assert payload['launch_id'] == 'synthetic-launch'
    assert payload['service'] == 'project-app'
    assert payload['pid'] > 0
