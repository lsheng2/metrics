import json
from pathlib import Path
import subprocess
import sys

from ai_base_runtime.testkit import scripted_model_endpoint
from ai_base_runtime.testkit.host_support._domain_assertions import _response


ROOT = Path(__file__).resolve().parents[2]


class ApprovalRequest(dict):
    def __call__(self, request):
        assert len(request["tools"]) == 1
        return _response(tool_name=request["tools"][0]["function"]["name"])


def test_context_exit_then_os_exit_preserves_runs_sessions_approvals(tmp_path):
    responses = [_response('{"answer":"task-complete"}'), ApprovalRequest(), _response("approved-complete")]
    with scripted_model_endpoint(responses) as model:
        for mode in ("write", "read"):
            command = [
                sys.executable, "-I", str(ROOT / "ai_host/tests/runtime_recovery_entry.py"),
                str(tmp_path), "0", str(tmp_path / "unused-stop"), mode, model.model.base_url,
            ]
            result = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            (tmp_path / f"{mode}.stdout").write_text(result.stdout, encoding="utf-8")
            (tmp_path / f"{mode}.stderr").write_text(result.stderr, encoding="utf-8")
            assert result.returncode == 0, result.stdout + result.stderr
            assert len(model.requests) == 3
        restored = json.loads((tmp_path / "recovery-read.json").read_text(encoding="utf-8"))
        assert restored["reacquired_runtime"] is True and restored["new_effects"] == 0
        assert model.remaining == 0
