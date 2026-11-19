from pathlib import Path

from scripts.validation import qualify_ai_runtime as qualifier


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
