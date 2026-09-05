from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import audit_stack_boot_logs


def test_shouldFailBootAuditWhenDashboardServiceLogContainsError(tmp_path, capsys):
    log_path = tmp_path / "state" / "e2e" / "service-lifecycle-engine" / "logs" / "grafana-3001.out.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        'logger=http.server level=error msg="failed to open listener" error="forbidden by access permissions"\n',
        encoding="utf-8",
    )
    state_path = tmp_path / "state" / "e2e" / "service-lifecycle-engine" / "metrics-bug-trend-default.json"
    state_path.write_text(
        json.dumps(
            {
                "services": {
                    "grafana": {
                        "stdout_log": str(log_path),
                        "stderr_log": str(log_path.with_suffix(".err.log")),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--require-dashboard-state",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Boot log audit failed" in output
    assert "grafana-3001.out.log:1" in output
    assert "forbidden by access permissions" in output


def test_shouldReportBootWarningsWithoutFailingAudit(tmp_path, capsys):
    log_path = tmp_path / "stack.log"
    log_path.write_text("InsecureRequestWarning: Unverified HTTPS request is being made.\n", encoding="utf-8")

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit warnings" in output
    assert "InsecureRequestWarning" in output


def test_shouldIgnoreKnownGrafanaClientAbortNoise(tmp_path, capsys):
    log_path = tmp_path / "grafana-3001.out.log"
    log_path.write_text(
        'logger=context userId=1 orgId=1 uname=admin level=error msg="Request error" error="net/http: abort Handler"\n',
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output
    assert "abort Handler" not in output


def test_shouldAcceptAiBaseStateWrittenWithUtf8Bom(tmp_path, capsys):
    ai_base_workspace = tmp_path / "ai-base"
    state_path = ai_base_workspace / ".tmp-validation" / "runtime" / "dev-stack-state.dashboard_query_agent.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"startup": {"state": "ready", "lastError": None}}), encoding="utf-8-sig")

    exit_code = audit_stack_boot_logs.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--require-ai-base-state",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output


def test_shouldIgnoreAlreadyRunningSyncCommandErrorAsBenign(tmp_path, capsys):
    log_path = tmp_path / "jira-profile-sync.log"
    log_path.write_text(
        "\n".join(
            [
                "python.exe : CommandError: A sync is already running for this scope.",
                "At C:\\repo\\scripts\\e2e_dashboard_ai_stack.ps1:46 char:9",
                "+         & $FilePath @Arguments 2>&1 | Tee-Object -FilePath $logPath",
                "+         ~~~~~~~~~~~~~~~~~~~~~~~~~~~",
                "    + CategoryInfo          : NotSpecified: (CommandError: A...for this scope.:String) [], RemoteException",
                "    + FullyQualifiedErrorId : NativeCommandError",
            ]
        ),
        encoding="utf-16",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output
    assert "A sync is already running for this scope" not in output


def test_shouldIgnoreKnownGrafanaStartupWarnings(tmp_path, capsys):
    log_path = tmp_path / "grafana-3001.out.log"
    log_path.write_text(
        "\n".join(
            [
                'logger=sqlstore level=warn msg="SQLite database file has broader permissions than it should" path="grafana.db" mode=-rw-rw-rw- expected=-rw-r-----',
                'level=warn msg="skipped registering status sub-resource that does not support dual writing" resource=alertrules.rules.alerting.grafana.app',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output
    assert "SQLite database file has broader permissions" not in output


def test_shouldIgnoreGrafanaDatasourceErrorsFromStaleClientDashboardQuery(tmp_path, capsys):
    log_path = tmp_path / "grafana-3001.out.log"
    log_path.write_text(
        "\n".join(
            [
                'logger=plugin.yesoreyeram-infinity-datasource level=error msg="Partial data response error" pluginId=yesoreyeram-infinity-datasource endpoint=queryData error="error while performing the infinity query. unsuccessful HTTP response code\\nstatus code : 400 Bad Request" statusSource=downstream',
                'logger=plugin.yesoreyeram-infinity-datasource level=error msg="Plugin Request Completed" dsUid=metrics-bug-trend-api endpoint=queryData pluginId=yesoreyeram-infinity-datasource statusSource=downstream status=error',
            ]
        ),
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output
    assert "Partial data response error" not in output


def test_shouldIgnoreWindowsProactorClientResetTraceback(tmp_path, capsys):
    log_path = tmp_path / "backend.err.log"
    log_path.write_text(
        "\n".join(
            [
                "INFO:     Application startup complete.",
                "Exception in callback _ProactorBasePipeTransport._call_connection_lost()",
                "handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>",
                "Traceback (most recent call last):",
                '  File "C:\\Program Files\\Python314\\Lib\\asyncio\\events.py", line 94, in _run',
                "    self._context.run(self._callback, *self._args)",
                '  File "C:\\Program Files\\Python314\\Lib\\asyncio\\proactor_events.py", line 165, in _call_connection_lost',
                "    self._sock.shutdown(socket.SHUT_RDWR)",
                "ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Boot log audit passed" in output
    assert "Traceback" not in output


def test_shouldStillFailUnexpectedTraceback(tmp_path, capsys):
    log_path = tmp_path / "backend.err.log"
    log_path.write_text(
        "\n".join(
            [
                "Exception in callback unexpected_callback()",
                "Traceback (most recent call last):",
                "RuntimeError: broken startup",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = audit_stack_boot_logs.main(["--dashboard-workspace", str(tmp_path), "--log-file", str(log_path)])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Boot log audit failed" in output
    assert "unexpected_callback" in output
    assert "Traceback (most recent call last)" in output


def test_shouldScanAiBaseHeadlessRuntimeLogs(tmp_path, capsys):
    ai_base_workspace = tmp_path / "ai-base"
    state_path = ai_base_workspace / ".tmp-validation" / "runtime" / "dev-stack-state.dashboard_query_agent.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"startup": {"state": "ready", "lastError": None}}), encoding="utf-8")
    log_path = ai_base_workspace / ".tmp-validation" / "runtime" / "logs" / "backend.err.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("ERROR: backend failed to bind\n", encoding="utf-8")

    exit_code = audit_stack_boot_logs.main(
        [
            "--dashboard-workspace",
            str(tmp_path),
            "--ai-base-workspace",
            str(ai_base_workspace),
            "--require-ai-base-state",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "backend.err.log" in output
    assert "backend failed to bind" in output
