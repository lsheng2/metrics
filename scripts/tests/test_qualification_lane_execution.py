import json
from pathlib import Path
import subprocess

import pytest

from scripts.validation import qualify_ai_runtime as qualifier


def _successful_pytest_subprocess(monkeypatch, observed_timeouts: list[int | None]):
    def fake_run(argv, cwd=None, capture_output=True, text=True, timeout=None, env=None, stdout=None, stderr=None):
        from scripts.tests.test_qualify_ai_runtime import _write_inventory

        command = [str(part) for part in argv]
        observed_timeouts.append(timeout)
        junit = Path(command[command.index('--junitxml') + 1])
        junit.parent.mkdir(parents=True, exist_ok=True)
        junit.write_text(
            '<testsuite tests="1" failures="0" errors="0" skipped="0">'
            '<testcase classname="execution" name="owned_timeout"/></testsuite>',
            encoding='utf-8',
        )
        _write_inventory(
            Path(command[command.index('--execution-inventory') + 1]), command, Path(cwd),
            {'execution.py::owned_timeout': 'execution::owned_timeout'},
        )
        if stdout is not None:
            stdout.write('pytest stdout\n')
        if stderr is not None:
            stderr.write('')
        return subprocess.CompletedProcess(command, 0, stdout='pytest stdout\n', stderr='')

    monkeypatch.setattr(qualifier.subprocess, 'run', fake_run)


def _lane_command_receipt(run_root: Path, label: str) -> dict:
    return json.loads((run_root / 'logs' / f'{label}.command.json').read_text(encoding='utf-8'))


def test_qualifier_keeps_case_paths_short_and_under_owned_root(tmp_path, monkeypatch):
    from scripts.tests.test_qualify_ai_runtime import _base_case, _fake_subprocess

    case = _base_case(tmp_path, monkeypatch)
    commands = _fake_subprocess(monkeypatch)
    assert qualifier.main([
        '--profile', 'functional', '--inputs', str(case['inputs']), '--output', str(case['output']),
    ]) == 0
    basetemps = [
        Path(command[command.index('--basetemp') + 1])
        for command in commands if '--basetemp' in command
    ]
    assert len(basetemps) == len(qualifier.MODULE_LANES) + 1
    # UUID-heavy archive fixtures need headroom beyond the run directory itself.
    for path in basetemps:
        relative = path.relative_to(case['owned'])
        assert len(relative.as_posix()) <= 50, str(relative)


def test_lane_creates_basetemp_parent_before_launch(tmp_path, monkeypatch):
    run_root = tmp_path / 'qualification'

    def execute(argv, **kwargs):
        from scripts.tests.test_qualify_ai_runtime import _write_inventory

        basetemp = Path(argv[argv.index('--basetemp') + 1])
        assert basetemp.parent.is_dir(), 'pytest cannot create basetemp without its parent'
        assert not basetemp.exists(), 'pytest owns the fresh basetemp directory'
        junit = Path(argv[argv.index('--junitxml') + 1])
        junit.parent.mkdir(parents=True, exist_ok=True)
        junit.write_text(
            '<testsuite tests="1" failures="0" errors="0" skipped="0">'
            '<testcase classname="execution" name="owned_parent"/></testsuite>',
            encoding='utf-8',
        )
        _write_inventory(
            Path(argv[argv.index('--execution-inventory') + 1]), argv, qualifier.ROOT,
            {'execution.py::owned_parent': 'execution::owned_parent'},
        )
        return {'argv': argv, 'returncode': 0}

    monkeypatch.setattr(qualifier, 'run_command', execute)
    result = qualifier.run_pytest_lane(
        Path('candidate-python'), 'scripts/tests/test_qualification_lane_execution.py',
        run_root=run_root, label='module',
    )
    assert result['junit']['tests'] == 1
    assert result['basetemp'] == str(run_root / 'basetemp' / 'module')


def test_full_project_management_lane_receipt_uses_authorized_aggregate_timeout(tmp_path, monkeypatch):
    observed_timeouts: list[int | None] = []
    _successful_pytest_subprocess(monkeypatch, observed_timeouts)
    run_root = tmp_path / 'qualification'

    result = qualifier.run_pytest_lane(
        Path('candidate-python'), 'project_management/tests',
        run_root=run_root, label='full-project-management',
    )

    receipt = _lane_command_receipt(run_root, 'full-project-management')
    assert result['junit']['tests'] == 1
    assert receipt['timeout_seconds'] == 7200
    assert observed_timeouts == [7200]
    assert 'project_management/tests' in receipt['argv']
    assert '--timeout' not in receipt['argv']


@pytest.mark.parametrize('target', [
    'ai_host/tests/test_admission.py',
    'ai_host/tests',
    'metrics/tests',
    'bug_metrics/tests',
    'jira_sync/tests',
    'ui_web/tests',
    'scripts/tests',
    'project_management/tests/test_report_templates.py',
    'project_management/tests_extra',
    *qualifier.PERFORMANCE_TESTS,
])
def test_non_full_and_near_match_targets_keep_default_timeout_receipts(tmp_path, monkeypatch, target):
    observed_timeouts: list[int | None] = []
    _successful_pytest_subprocess(monkeypatch, observed_timeouts)
    run_root = tmp_path / 'qualification'
    label = f'target-{len(target)}'

    result = qualifier.run_pytest_lane(Path('candidate-python'), target, run_root=run_root, label=label)

    receipt = _lane_command_receipt(run_root, label)
    assert result['junit']['tests'] == 1
    assert receipt['timeout_seconds'] == 3600
    assert observed_timeouts == [3600]
    assert target in receipt['argv']
    assert '--timeout' not in receipt['argv']


def test_timeout_failure_still_writes_fail_closed_receipt_and_logs(tmp_path, monkeypatch):
    def timeout_run(argv, cwd=None, capture_output=True, text=True, timeout=None, env=None, stdout=None, stderr=None):
        if stdout is not None:
            stdout.write('partial stdout\n')
        if stderr is not None:
            stderr.write('partial stderr\n')
        raise subprocess.TimeoutExpired([str(part) for part in argv], timeout)

    monkeypatch.setattr(qualifier.subprocess, 'run', timeout_run)
    log_dir = tmp_path / 'logs'

    with pytest.raises(qualifier.QualificationError, match='timed out; cleanup uncertain'):
        qualifier.run_command(
            ['candidate-python', '-I', 'scripts/validation/run_report_authoring_tests.py', 'scripts/tests'],
            cwd=tmp_path, log_dir=log_dir, label='timeout-probe', timeout=5,
        )

    receipt = json.loads((log_dir / 'timeout-probe.command.json').read_text(encoding='utf-8'))
    assert receipt['timeout_seconds'] == 5
    assert receipt['timed_out'] is True
    assert receipt['cleanup_uncertain'] is True
    assert receipt['returncode'] is None
    assert Path(receipt['stdout']).read_text(encoding='utf-8') == 'partial stdout\n'
    assert Path(receipt['stderr']).read_text(encoding='utf-8') == 'partial stderr\n'
