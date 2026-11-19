from pathlib import Path

from scripts.validation import qualify_ai_runtime as qualifier


def test_lane_creates_basetemp_parent_before_launch(tmp_path, monkeypatch):
    run_root = tmp_path / 'qualification'

    def execute(argv, **kwargs):
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
        return {'argv': argv, 'returncode': 0}

    monkeypatch.setattr(qualifier, 'run_command', execute)
    result = qualifier.run_pytest_lane(
        Path('candidate-python'), 'scripts/tests/test_qualification_lane_execution.py',
        run_root=run_root, label='module',
    )
    assert result['junit']['tests'] == 1
    assert result['basetemp'] == str(run_root / 'basetemp' / 'module')
