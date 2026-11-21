from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SELECTED_WINDOWS_PYTHON = Path(sys.executable).resolve()
QUALIFIED_INFINITY_PLUGIN = Path("D:/AIGC/scrum_dashboard/state/grafana/data/plugins/yesoreyeram-infinity-datasource")
QUALIFIED_INFINITY_PLUGIN_JSON_SHA256 = "1133bd824b1b31bc77575b7bc728428541bc8833018336e9a95eb6ded4607d67"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import process_exists
from service_lifecycle_engine.platform_ops import is_port_available, kill_process


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell launcher coverage")


def configured_w1_artifact_root() -> Path:
    default = Path(tempfile.gettempdir()) / "scrum-dashboard-w1-launch-real-ps"
    return Path(os.environ.get("MDB2_W1_LAUNCH_ARTIFACT_ROOT", str(default)))


W1_ARTIFACT_ROOT = configured_w1_artifact_root()


def test_selected_windows_python_tracks_current_runner() -> None:
    assert SELECTED_WINDOWS_PYTHON == Path(sys.executable).resolve()


def test_w1_artifact_root_default_uses_owned_temp_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MDB2_W1_LAUNCH_ARTIFACT_ROOT", raising=False)
    root = configured_w1_artifact_root()
    assert root == Path(tempfile.gettempdir()) / "scrum-dashboard-w1-launch-real-ps"
    assert "mdb2-windows-20261117" not in root.parts


def test_w1_artifact_root_preserves_explicit_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    override = tmp_path / "explicit-artifacts"
    monkeypatch.setenv("MDB2_W1_LAUNCH_ARTIFACT_ROOT", str(override))
    assert configured_w1_artifact_root() == override


def test_local_backend_powershell_runs_real_start_stop_restart_on_requested_port() -> None:
    run_root = new_artifact_run_dir("local-backend-real-ps")
    source = run_root / "source"
    copy_source_tree(source)
    write_source_fingerprints(run_root / "source-fingerprints.before.json", source)
    assert not (source / ".env").exists()
    assert SELECTED_WINDOWS_PYTHON.exists()
    port = find_free_port()
    environment = synthetic_serve_environment(run_root, source_root=source)
    environment["METRICS_DASHBOARD_PYTHON"] = str(SELECTED_WINDOWS_PYTHON)
    command_log = run_root / "commands.jsonl"

    migrate_synthetic_database(environment, source, command_log)
    assert_command_log_uses_selected_python(command_log, "migrate")
    write_fixture_fingerprints(run_root / "fixture-fingerprints.after-migrate.json", run_root)
    service_config = json.loads((source / "scripts" / "e2e_bug_trend.services.json").read_text(encoding="utf-8"))
    django_config = next(service for service in service_config["services"] if service["name"] == "django")
    assert django_config["graceful_timeout_seconds"] >= 15
    assert django_config["command"][:6] == ["{python}", "manage.py", "serve", "--host", "127.0.0.1", "--port"]

    first_state = None
    second_state = None
    try:
        start1 = run_real_powershell(
            source / "scripts" / "local_start_backend.ps1",
            ["-Workspace", str(source), "-Port", str(port)],
            source,
            environment,
            command_log,
            "start-1",
        )
        assert start1.returncode == 0, start1.stderr + start1.stdout
        first_state = read_single_service_state(source)
        assert int(first_state["port"]) == port
        assert_service_state_uses_selected_python(first_state)
        assert "manage.py" in first_state["command"]
        assert "serve" in first_state["command"]
        assert "--stop-file" in first_state["command"]
        assert "grafana" not in read_single_state_payload(source).get("services", {})
        assert_http_ok(f"http://127.0.0.1:{port}/ai/")

        stop1 = run_real_powershell(
            source / "scripts" / "local_stop_backend.ps1",
            ["-Workspace", str(source), "-Port", str(port)],
            source,
            environment,
            command_log,
            "stop-1",
        )
        assert stop1.returncode == 0, stop1.stderr + stop1.stdout
        assert_stop_command_cleanup(source, port, first_state)

        start2 = run_real_powershell(
            source / "scripts" / "local_start_backend.ps1",
            ["-Workspace", str(source), "-Port", str(port)],
            source,
            environment,
            command_log,
            "start-2",
        )
        assert start2.returncode == 0, start2.stderr + start2.stdout
        second_state = read_single_service_state(source)
        assert int(second_state["port"]) == port
        assert_service_state_uses_selected_python(second_state)
        assert int(second_state["pid"]) != int(first_state["pid"])
        assert_http_ok(f"http://127.0.0.1:{port}/ai/")

        stop2 = run_real_powershell(
            source / "scripts" / "local_stop_backend.ps1",
            ["-Workspace", str(source), "-Port", str(port)],
            source,
            environment,
            command_log,
            "stop-2",
        )
        assert stop2.returncode == 0, stop2.stderr + stop2.stdout
        assert_stop_command_cleanup(source, port, second_state)
        write_source_fingerprints(run_root / "source-fingerprints.after.json", source)
        write_fixture_fingerprints(run_root / "fixture-fingerprints.after.json", run_root)
    finally:
        cleanup = run_real_powershell(
            source / "scripts" / "local_stop_backend.ps1",
            ["-Workspace", str(source), "-Port", str(port)],
            source,
            environment,
            command_log,
            "cleanup-stop",
            timeout=60,
        )
        (run_root / "cleanup-stop.returncode").write_text(str(cleanup.returncode), encoding="utf-8")
        for state in (first_state, second_state):
            if state and process_exists(int(state["pid"])):
                kill_process(int(state["pid"]))
        assert_no_w1_processes(source)


def test_e2e_start_stop_powershell_runs_real_dashboard_and_grafana_on_owned_ports() -> None:
    grafana_bin = Path(r"C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe")
    assert grafana_bin.exists(), "local Grafana binary is required for native E2E launcher coverage"
    run_root = new_artifact_run_dir("e2e-real-ps")
    source = run_root / "source"
    copy_source_tree(source)
    write_source_fingerprints(run_root / "source-fingerprints.before.json", source)
    django_port = find_free_port()
    grafana_port = find_free_port()
    environment = synthetic_serve_environment(run_root, source_root=source)
    environment["METRICS_DASHBOARD_PYTHON"] = str(SELECTED_WINDOWS_PYTHON)
    environment["GRAFANA_BIN"] = str(grafana_bin)
    plugin_dir = copy_qualified_infinity_plugin(run_root)
    environment["GRAFANA_PLUGINS_PATH"] = str(plugin_dir)
    environment["GF_PATHS_PLUGINS"] = str(plugin_dir)
    command_log = run_root / "commands.jsonl"

    try:
        start = run_real_powershell(
            source / "scripts" / "e2e_start_bug_trend.ps1",
            [
                "-Workspace",
                str(source),
                "-OpenEntrypoint",
                "none",
                "-DjangoPort",
                str(django_port),
                "-GrafanaPort",
                str(grafana_port),
            ],
            source,
            environment,
            command_log,
            "e2e-start",
            timeout=180,
        )
        assert start.returncode == 0, start.stderr + start.stdout
        summary = json.loads((source / "state" / "e2e" / "bug_trend_ports.json").read_text(encoding="utf-8"))
        assert summary["django_port"] == django_port
        assert summary["grafana_port"] == grafana_port
        assert_django_state_uses_selected_python(source)
        assert_http_ok(f"http://127.0.0.1:{django_port}/ai/")
        assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/health")

        stop = run_real_powershell(
            source / "scripts" / "e2e_stop_bug_trend.ps1",
            [
                "-Workspace",
                str(source),
                "-DjangoPort",
                str(django_port),
                "-GrafanaPort",
                str(grafana_port),
            ],
            source,
            environment,
            command_log,
            "e2e-stop",
            timeout=90,
        )
        assert stop.returncode == 0, stop.stderr + stop.stdout
        records = termination_records(source)
        assert {records[-2]["service"], records[-1]["service"]} == {"django", "grafana"}
        assert all(record["stopped"] for record in records[-2:])
        assert all(not record["force_requested"] for record in records[-2:])
        by_service = {record["service"]: record for record in records[-2:]}
        assert by_service["django"]["reason"] == "stop_command"
        assert by_service["django"]["forced"] is False
        assert by_service["grafana"]["reason"] == "stop_command"
        assert by_service["grafana"]["forced"] is False
        assert by_service["django"]["exit_code"] == 0
        assert by_service["grafana"]["exit_code"] == 0
        write_source_fingerprints(run_root / "source-fingerprints.after.json", source)
        write_fixture_fingerprints(run_root / "fixture-fingerprints.after.json", run_root)
    finally:
        cleanup = run_real_powershell(
            source / "scripts" / "e2e_stop_bug_trend.ps1",
            [
                "-Workspace",
                str(source),
                "-DjangoPort",
                str(django_port),
                "-GrafanaPort",
                str(grafana_port),
            ],
            source,
            environment,
            command_log,
            "cleanup-stop",
            timeout=90,
        )
        (run_root / "cleanup-stop.returncode").write_text(str(cleanup.returncode), encoding="utf-8")
        assert_no_w1_processes(source)


def copy_qualified_infinity_plugin(run_root: Path) -> Path:
    plugin_json = QUALIFIED_INFINITY_PLUGIN / "plugin.json"
    assert plugin_json.is_file(), f"qualified Infinity plugin is missing: {plugin_json}"
    assert sha256_file(plugin_json) == QUALIFIED_INFINITY_PLUGIN_JSON_SHA256
    plugin_root = run_root / "grafana-plugins"
    plugin_root.mkdir()
    target = plugin_root / QUALIFIED_INFINITY_PLUGIN.name
    shutil.copytree(QUALIFIED_INFINITY_PLUGIN, target)
    inventory = {
        "source": str(QUALIFIED_INFINITY_PLUGIN),
        "target": str(target),
        "plugin_json_sha256": sha256_file(target / "plugin.json"),
        "files": {
            item.relative_to(plugin_root).as_posix(): {
                "sha256": sha256_file(item),
                "bytes": item.stat().st_size,
            }
            for item in sorted(plugin_root.rglob("*"))
            if item.is_file()
        },
    }
    (run_root / "grafana-plugin-inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")
    return plugin_root


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def new_artifact_run_dir(prefix: str) -> Path:
    run_dir = W1_ARTIFACT_ROOT / f"{prefix}-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def copy_source_tree(destination: Path) -> None:
    from scripts.validation.project_full_stack_support import reject_reparse_components

    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], check=True, capture_output=True, timeout=30,
    )
    names = set(tracked.stdout.decode("utf-8").split("\0")) - {""}
    plan = ROOT / "openspec/changes/embed-ai-base-runtime-in-process/windows-close-dag.json"
    names.update(json.loads(plan.read_text(encoding="utf-8"))["planned_paths"])
    selected = []
    for name in sorted(names):
        relative = Path(name)
        if relative.anchor or ".." in relative.parts:
            raise ValueError("Source export path must be repository-relative")
        if relative.parts[0] in {"state", "logs", "screenshots", "tmp_ui_validation", ".tmp"}:
            continue
        if relative.name.startswith(".env") and relative.name != ".env.example":
            continue
        if relative.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".key", ".pem", ".pyc", ".pyo"}:
            continue
        source = ROOT / relative
        reject_reparse_components(source)
        if source.is_file():
            selected.append((source, destination / relative))
    destination.mkdir(parents=True)
    for source, target in selected:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def run_real_powershell(
    script: Path,
    args: list[str],
    cwd: Path,
    environment: dict[str, str],
    command_log: Path,
    label: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    append_command_record(command_log, label, completed)
    return completed


def append_command_record(command_log: Path, label: str, completed: subprocess.CompletedProcess[str]) -> None:
    command_log.parent.mkdir(parents=True, exist_ok=True)
    with command_log.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "label": label,
                    "args": list(map(str, completed.args)),
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                sort_keys=True,
            )
            + "\n"
        )


def runtime_state_files(source: Path) -> list[Path]:
    return sorted((source / "state" / "local" / "instances").glob("*/service-lifecycle-engine/metrics-bug-trend-*.json"))


def read_single_state_payload(source: Path) -> dict[str, object]:
    state_files = runtime_state_files(source)
    assert len(state_files) == 1, state_files
    return json.loads(state_files[0].read_text(encoding="utf-8"))


def read_single_service_state(source: Path) -> dict[str, object]:
    services = read_single_state_payload(source)["services"]
    assert set(services) == {"django"}
    return services["django"]


def termination_records(source: Path) -> list[dict[str, object]]:
    ledgers = sorted((source / "state" / "local" / "instances").glob("*/service-lifecycle-engine/termination-ledger.jsonl"))
    assert len(ledgers) == 1, ledgers
    return [json.loads(line) for line in ledgers[0].read_text(encoding="utf-8").splitlines() if line.strip()]


def assert_service_state_uses_selected_python(state: dict[str, object]) -> None:
    command = state["command"]
    assert isinstance(command, list)
    assert Path(command[0]).resolve() == SELECTED_WINDOWS_PYTHON


def assert_django_state_uses_selected_python(source: Path) -> None:
    services = read_single_state_payload(source)["services"]
    assert_service_state_uses_selected_python(services["django"])


def assert_command_log_uses_selected_python(command_log: Path, label: str) -> None:
    records = [
        json.loads(line)
        for line in command_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [record for record in records if record["label"] == label]
    assert len(matches) == 1, records
    assert Path(matches[0]["args"][0]).resolve() == SELECTED_WINDOWS_PYTHON


def assert_stop_command_cleanup(source: Path, port: int, state: dict[str, object]) -> None:
    records = termination_records(source)
    assert records[-1]["service"] == "django"
    assert records[-1]["port"] == port
    assert records[-1]["reason"] == "stop_command"
    assert records[-1]["forced"] is False
    assert records[-1]["force_requested"] is False
    assert records[-1]["exit_code"] == 0
    assert not process_exists(int(state["pid"]))
    assert is_port_available("127.0.0.1", port)
    stdout = Path(str(state["stdout_log"])).read_text(encoding="utf-8", errors="replace")
    stderr = Path(str(state["stderr_log"])).read_text(encoding="utf-8", errors="replace")
    assert "serve forced exit" not in stdout
    assert "Traceback (most recent call last)" not in stdout + stderr
    assert '"event":"project_runtime_absent"' in stdout or '"event":"project_runtime_stopped"' in stdout


def assert_http_ok(url: str) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with opener.open(url, timeout=2) as response:
                assert 200 <= response.status < 500
                response.read(512)
                return
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(0.2)
    raise AssertionError(f"URL did not respond: {url}: {last_error}")


def assert_no_w1_processes(source: Path) -> None:
    escaped_source = str(source).replace("'", "''")
    script = (
        f"$source = '{escaped_source}'; "
        "$hits = @(Get-CimInstance Win32_Process | Where-Object { "
        "$cmd = [string]$_.CommandLine; "
        "$_.ProcessId -ne $PID -and $_.Name -like 'python*' -and "
        "$cmd.Contains($source) -and $cmd.Contains('manage.py') -and $cmd.Contains('serve') "
        "} | Select-Object ProcessId,ParentProcessId,Name,CommandLine); "
        "if ($hits.Count -gt 0) { $hits | ConvertTo-Json -Depth 4; exit 1 }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def write_source_fingerprints(path: Path, source: Path) -> None:
    tracked = [
        "manage.py",
        "scripts/e2e_bug_trend.py",
        "scripts/e2e_bug_trend.services.json",
        "scripts/local_start_backend.ps1",
        "scripts/local_stop_backend.ps1",
        "scripts/service_lifecycle_engine/engine.py",
        "scripts/service_lifecycle_engine/stopping.py",
        "scripts/service_lifecycle_engine/starting.py",
    ]
    payload = {
        "root": str(source),
        "files": {
            name: {
                "sha256": sha256_file(source / name),
                "bytes": (source / name).stat().st_size,
            }
            for name in tracked
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_fixture_fingerprints(path: Path, run_root: Path) -> None:
    files = sorted(
        item
        for item in (run_root / "synthetic-app").rglob("*")
        if item.is_file()
    )
    payload = {
        "root": str(run_root / "synthetic-app"),
        "files": {
            item.relative_to(run_root).as_posix(): {
                "sha256": sha256_file(item),
                "bytes": item.stat().st_size,
            }
            for item in files
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




def synthetic_serve_environment(tmp_path: Path, *, source_root: Path = ROOT) -> dict[str, str]:
    synthetic_root = tmp_path / "synthetic-app"
    synthetic_root.mkdir()
    settings_path = tmp_path / "synthetic_dashboard_settings.py"
    settings_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import os",
                "from unittest.mock import patch",
                "root = Path(os.environ['W1_SYNTHETIC_ROOT'])",
                "(root / 'state').mkdir(parents=True, exist_ok=True)",
                "(root / 'archive').mkdir(parents=True, exist_ok=True)",
                "(root / 'static').mkdir(parents=True, exist_ok=True)",
                "os.environ.update({",
                "    'METRICS_STATE_DIR': str(root / 'state'),",
                "    'METRICS_SQLITE_DATABASE_PATH': str(root / 'catalog.sqlite3'),",
                "    'METRICS_TASK_SEARCH_CACHE_DIR': str(root / 'task-cache'),",
                "    'METRICS_PROJECT_ARCHIVE_ROOT': str(root / 'archive'),",
                "    'METRICS_JIRA_SERVER_URL': 'https://synthetic-jira.example.test',",
                "    'METRICS_JIRA_AUTH_MODE': 'server_pat',",
                "    'METRICS_JIRA_API_TOKEN': 'synthetic-only-token',",
                "    'SECRET_KEY': 'synthetic-w1-launch-only',",
                "    'DEBUG': 'true',",
                "})",
                "with patch('environs.Env.read_env', lambda self, *args, **kwargs: None):",
                "    from metrics.settings.defaults_metrics import *  # noqa: F401,F403",
                "ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']",
                "DATABASES['default']['NAME'] = str(root / 'catalog.sqlite3')",
                "STATIC_ROOT = root / 'static'",
                "METRICS_PROJECT_RUN_ENABLED = False",
                "METRICS_PROJECT_ARCHIVE_ROOT = str(root / 'archive')",
                "METRICS_PROJECT_ARCHIVE_AUTHOR_NAME = 'Synthetic W1 Launch'",
                "METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL = 'synthetic@example.test'",
                "METRICS_BASIC_AUTH_USERS = None",
                "METRICS_AI_MODEL_BASE_URL = ''",
                "METRICS_AI_MODEL_NAME = ''",
                "METRICS_AI_MODEL_API_KEY = ''",
                "PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    inherited_keys = ("COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR")
    environment = {key: value for key, value in os.environ.items() if key.upper() in inherited_keys}
    environment.update(
        DJANGO_SETTINGS_MODULE="synthetic_dashboard_settings",
        PYTHONNOUSERSITE="1",
        PYTHONPATH=os.pathsep.join([str(tmp_path), str(source_root)]),
        PYTHONUTF8="1",
        W1_SYNTHETIC_ROOT=str(synthetic_root),
    )
    return environment


def migrate_synthetic_database(environment: dict[str, str], source_root: Path = ROOT, command_log: Path | None = None) -> None:
    completed = subprocess.run(
        [str(SELECTED_WINDOWS_PYTHON), str(source_root / "manage.py"), "migrate", "--noinput", "--verbosity", "0"],
        cwd=source_root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if command_log is not None:
        append_command_record(command_log, "migrate", completed)
    assert Path(completed.args[0]).resolve() == SELECTED_WINDOWS_PYTHON
    completed.check_returncode()
