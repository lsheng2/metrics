import json

import pytest

from scripts.tests.test_windows_host_conformance import (
    _case, _command_record, _process, _server_records, _signals, _sha, _write_json,
)
from scripts.validation import windows_host_conformance_evidence as evidence
from scripts.validation.windows_qualification_inputs import QualificationError


@pytest.mark.parametrize("code,expected", [(1, 0), (1, 1), (0, 1), (False, 0)])
def test_native_command_requires_integer_zero_actual_and_expected_exit(tmp_path, code, expected):
    argv = ["python", "synthetic"]
    record = _command_record(tmp_path, "probe", argv, evidence.ROOT)
    record.update(returncode=code, expected_returncode=expected)
    with open(record["receipt"], "w", encoding="utf-8") as output:
        json.dump({key: value for key, value in record.items() if key != "receipt"}, output)
    with pytest.raises(QualificationError):
        evidence._command(record, tmp_path, label="probe", argv=argv)


@pytest.mark.parametrize("elapsed", [float("nan"), -1, True, 2.1])
def test_http_close_requires_finite_nonnegative_elapsed_within_grace(elapsed):
    records = _server_records()
    stopped = next(row for row in records if row["event"] == "stream_stop_finished")
    stopped["outcome"]["http_result"]["elapsed_seconds"] = elapsed
    with pytest.raises(QualificationError):
        evidence._server({"server": records})


@pytest.mark.parametrize("case_name,helper_code", [("drain-stop-file", 0), ("normal-stop-file", 7)])
def test_force_stop_accepts_a_completed_helper_without_changing_host_exit_contract(tmp_path, case_name, helper_code):
    paths = _signals(tmp_path)
    changed = next(path for path in paths if case_name in str(path))
    payload = json.loads(changed.read_text(encoding="utf-8"))
    payload["descendants"].append([789, 2.0])
    payload["descendant_exit_codes"]["789"] = helper_code
    _write_json(changed, payload)
    refs = [{
        "path": str(path), "sha256": _sha(path),
        "log": {"path": str(path.with_name("serve.log")), "sha256": _sha(path.with_name("serve.log"))},
    } for path in paths]
    assert evidence._validate_signals(refs, tmp_path) == {"cases": 16}


@pytest.mark.parametrize("mutation", ["missing_exit", "unknown_exit", "boolean_exit", "host_exit", "late_host"])
def test_signal_proof_rejects_incomplete_descendants_or_weakened_host_contract(tmp_path, mutation):
    paths = _signals(tmp_path)
    changed = next(path for path in paths if "drain-stop-file" in str(path))
    payload = json.loads(changed.read_text(encoding="utf-8"))
    if mutation == "missing_exit":
        payload["descendant_exit_codes"] = {}
    elif mutation == "unknown_exit":
        payload["descendant_exit_codes"]["456"] = None
    elif mutation == "boolean_exit":
        payload["descendant_exit_codes"]["456"] = False
    elif mutation == "host_exit":
        payload["returncode"] = 0
    else:
        payload["elapsed"] = 1.1
    _write_json(changed, payload)
    refs = [{
        "path": str(path), "sha256": _sha(path),
        "log": {"path": str(path.with_name("serve.log")), "sha256": _sha(path.with_name("serve.log"))},
    } for path in paths]
    with pytest.raises(QualificationError):
        evidence._validate_signals(refs, tmp_path)


def test_b5_process_requires_child_termination_not_child_business_success(tmp_path, monkeypatch):
    from pathlib import Path

    case = _case(tmp_path, monkeypatch)
    directory = case["owned"] / "stream"
    directory.mkdir()
    python = Path(case["manifest"]["python"]["candidate"])
    _process(directory, python, case["root"], "stop-file")
    path = directory / "process.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["descendant_exit_codes"]["456"] = 7
    _write_json(path, payload)
    result = evidence._process(path, {"_paths": {"python": python}}, "stop-file")
    assert result["returncode"] == 0 and result["descendant_exit_codes"]["456"] == 7
