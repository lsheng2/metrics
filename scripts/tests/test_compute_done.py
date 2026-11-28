from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "compute_done.py"
SPEC = importlib.util.spec_from_file_location("compute_done", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
compute_done = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compute_done
SPEC.loader.exec_module(compute_done)

SAMPLE_TESTS = '''
import pytest


def test_passes():
    pass


@pytest.mark.parametrize("value", ["a/b::c"])
def test_param(value):
    pass


class TestGroup:
    def test_inside(self):
        pass


def test_fails():
    assert False


@pytest.mark.skip(reason="not ready")
def test_skipped():
    pass
'''


def _write_features(path: Path, *features: dict) -> Path:
    path.write_text(json.dumps({"change": "sample", "features": list(features)}), encoding="utf-8-sig")
    return path


def _feature(feature_id: str, *tests: str) -> dict:
    return {"id": feature_id, "behavior": f"behavior {feature_id}", "acceptance_tests": list(tests)}


def _junit(path: Path, *cases: str) -> Path:
    path.write_text(f'<testsuites><testsuite name="s">{"".join(cases)}</testsuite></testsuites>', encoding="utf-8")
    return path


def test_pytest_node_ids_match_real_junit_and_only_passes_count(tmp_path, capsys):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    sample = tmp_path / "tests" / "acceptance" / "test_sample.py"
    sample.parent.mkdir(parents=True)
    sample.write_text(SAMPLE_TESTS, encoding="utf-8")
    junit = tmp_path / "junit.xml"
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/acceptance/test_sample.py", f"--junitxml={junit}",
         "-q", "-p", "no:cacheprovider", "-p", "no:django"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    node = "tests/acceptance/test_sample.py::"
    features = _write_features(
        tmp_path / "feature_list.json",
        _feature("F-1", f"{node}test_passes", f"{node}test_param[a/b::c]", f"{node}TestGroup::test_inside"),
        _feature("F-2", f"{node}test_fails"),
        _feature("F-3", f"{node}test_skipped"),
    )

    assert compute_done.main(["compute_done.py", str(features), str(junit)]) == 1
    out = capsys.readouterr().out
    assert "DONE  F-1  behavior F-1" in out
    assert f"OPEN  F-2  behavior F-2\n      fail    {node}test_fails" in out
    assert f"OPEN  F-3  behavior F-3\n      skipped {node}test_skipped" in out
    assert "1/3 features done" in out


def test_worst_status_wins_across_reports_and_untested_features_stay_open(tmp_path, capsys):
    first = _junit(
        tmp_path / "pytest.xml",
        '<testcase classname="pkg.test_x" name="test_y"/>',
        '<testcase classname="evals.report" name="case-1"/>',
    )
    second = _junit(tmp_path / "rerun.xml", '<testcase classname="pkg.test_x" name="test_y"><skipped/></testcase>')
    features = _write_features(
        tmp_path / "feature_list.json",
        _feature("F-1", "evals.report::case-1"),
        _feature("F-2", "pkg/test_x.py::test_y"),
        _feature("F-3"),
        _feature("F-4", "pkg/test_x.py::test_missing"),
    )

    assert compute_done.main(["compute_done.py", str(features), str(first), str(second)]) == 1
    out = capsys.readouterr().out
    assert "DONE  F-1" in out
    assert "OPEN  F-2  behavior F-2\n      skipped pkg/test_x.py::test_y" in out
    assert "OPEN  F-3  behavior F-3\n      no acceptance tests" in out
    assert "OPEN  F-4  behavior F-4\n      missing pkg/test_x.py::test_missing" in out


def test_exit_codes_for_done_empty_and_usage(tmp_path, capsys):
    junit = _junit(tmp_path / "junit.xml", '<testcase classname="evals.report" name="case-1"/>')
    done = _write_features(tmp_path / "done.json", _feature("F-1", "evals.report::case-1"))
    empty = _write_features(tmp_path / "empty.json")

    assert compute_done.main(["compute_done.py", str(done), str(junit)]) == 0
    assert "1/1 features done" in capsys.readouterr().out
    assert compute_done.main(["compute_done.py", str(empty), str(junit)]) == 1
    assert compute_done.main(["compute_done.py", str(done)]) == 2
