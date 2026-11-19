from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.tests.test_windows_host_conformance import _case, _command_record, _sha, _valid_receipt, _write_json
from scripts.validation import windows_host_conformance as driver
from scripts.validation import windows_host_conformance_evidence as evidence
from scripts.validation import windows_qualification_inputs as inputs
from scripts.validation.windows_qualification_inputs import QualificationError
from scripts.validation import windows_host_conformance_environment as environment


def test_native_input_requires_a_frozen_candidate_environment(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    case["manifest"]["python"].pop("environments", None)
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError, match="environment"):
        driver.load_request(case["inputs"], case["output"])


def test_native_receipt_requires_before_and_after_environment_proof(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    request = inputs.load_request(case["inputs"], case["output"], profile="functional")
    receipt, _ = _valid_receipt(case)
    receipt.pop("environments", None)
    with pytest.raises(QualificationError, match="environment"):
        evidence.validate_result(receipt, request)


def test_actual_capture_drift_is_not_accepted_as_frozen_environment(tmp_path, monkeypatch):
    case = _case(tmp_path, monkeypatch)
    request = inputs.load_request(case["inputs"], case["output"], profile="functional")
    observed = deepcopy(environment.expected_environment(request))
    observed["packages"]["ai-base-runtime"]["version"] = "different"
    monkeypatch.setattr(environment, "capture_environment", lambda *_: (observed, {}))
    with pytest.raises(QualificationError, match="environment changed"):
        environment.capture(request, case["owned"] / "probe")


@pytest.mark.parametrize("mutation", ["distribution", "interpreter", "stdout"])
def test_environment_replay_binds_resolution_and_actual_probe_command(tmp_path, monkeypatch, mutation):
    case = _case(tmp_path, monkeypatch)
    request = inputs.load_request(case["inputs"], case["output"], profile="functional")
    expected = environment.expected_environment(request)
    run = case["owned"] / "probe"
    command = _command_record(
        run, "environment", [str(request["_paths"]["python"]), "-I", "-c", environment.ENVIRONMENT_PROBE],
        case["root"], expected,
    )
    reference = {
        "path": command["stdout"], "sha256": command["stdout_sha256"],
        "command": {"path": command["receipt"], "sha256": _sha(Path(command["receipt"]))},
    }
    if mutation == "distribution":
        expected["packages"]["ai-base-runtime"]["record_sha256"] = "changed"
        path = _write_json(Path(command["stdout"]), expected)
        reference["sha256"] = _sha(path)
    elif mutation == "interpreter":
        path = Path(command["receipt"])
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["argv"][0] = str(case["owned"] / "other-python.exe")
        _write_json(path, saved)
        reference["command"]["sha256"] = _sha(path)
    else:
        path = _write_json(run / "unrelated.json", expected)
        reference.update(path=str(path), sha256=_sha(path))
    with pytest.raises(QualificationError):
        environment.validate(reference, request, run, command_check=evidence._command)
