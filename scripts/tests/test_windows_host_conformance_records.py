import json

import pytest

from scripts.tests.test_windows_host_conformance import _command_record, _server_records
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
