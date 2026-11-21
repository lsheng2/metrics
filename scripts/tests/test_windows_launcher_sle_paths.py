from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SELECTED_WINDOWS_PYTHON = Path(sys.executable).resolve()
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec, process_exists
from service_lifecycle_engine.platform_ops import is_port_available, kill_process


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows SLE launcher coverage")


def test_selected_windows_python_tracks_current_runner() -> None:
    assert SELECTED_WINDOWS_PYTHON == Path(sys.executable).resolve()


def test_sle_launches_real_serve_and_stop_file_stops_normally(tmp_path: Path) -> None:
    port = find_free_port()
    stop_file = tmp_path / "serve.stop"
    environment = synthetic_serve_environment(tmp_path)
    migrate_synthetic_database(environment)
    lifecycle = ServiceLifecycleEngine(
        "test-project",
        ROOT,
        instance_name="w1-launch",
        state_directory=tmp_path / "state",
    )
    spec = real_serve_spec(tmp_path, [port], stop_file, environment)
    assert_serve_spec_uses_selected_python(spec)

    state = lifecycle.start_service(spec, port=port)
    try:
        assert Path(state.command[0]).resolve() == SELECTED_WINDOWS_PYTHON
        result = lifecycle.stop_service("django", graceful_timeout_seconds=5.0)
    finally:
        if process_exists(state.pid):
            kill_process(state.pid)

    assert result.stopped is True
    assert result.reason == "stop_command"
    assert result.forced is False
    assert result.exit_code == 0
    assert stop_file.exists()
    assert not process_exists(state.pid)
    assert is_port_available("127.0.0.1", port)


def test_sle_real_serve_start_reroutes_around_foreign_listener_and_preserves_it(tmp_path: Path) -> None:
    foreign = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    foreign.bind(("127.0.0.1", 0))
    foreign.listen(1)
    try:
        foreign_port = foreign.getsockname()[1]
        fallback_port = find_free_port()
        stop_file = tmp_path / "serve.stop"
        environment = synthetic_serve_environment(tmp_path)
        migrate_synthetic_database(environment)
        lifecycle = ServiceLifecycleEngine(
            "test-project",
            ROOT,
            instance_name="w1-launch",
            state_directory=tmp_path / "state",
        )
        spec = real_serve_spec(tmp_path, [foreign_port, fallback_port], stop_file, environment)
        assert_serve_spec_uses_selected_python(spec)

        state = lifecycle.start_service(spec)
        try:
            assert Path(state.command[0]).resolve() == SELECTED_WINDOWS_PYTHON
            assert state.port == fallback_port
            assert not is_port_available("127.0.0.1", foreign_port)
            result = lifecycle.stop_service("django", graceful_timeout_seconds=5.0)
        finally:
            if process_exists(state.pid):
                kill_process(state.pid)

        assert result.stopped is True
        assert not is_port_available("127.0.0.1", foreign_port)
    finally:
        foreign.close()


def test_sle_stuck_owned_process_escalates_after_grace_and_is_abnormal(tmp_path: Path) -> None:
    port = find_free_port()
    stop_file = tmp_path / "stuck.stop"
    cleanup_file = tmp_path / "stuck.cleanup"
    lifecycle = ServiceLifecycleEngine(
        "test-project",
        tmp_path,
        instance_name="w1-launch",
        state_directory=tmp_path / "state",
    )
    spec = ServiceSpec.from_values(
        "django",
        [port],
        [
            sys.executable,
            "-c",
            (
                "import pathlib, socket, sys, time; "
                "sock=socket.socket(); "
                "sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
                "sock.bind(('127.0.0.1', int(sys.argv[1]))); "
                "sock.listen()\n"
                "while not pathlib.Path(sys.argv[2]).exists(): time.sleep(0.02)"
            ),
            "{port}",
            str(cleanup_file),
        ],
        stop_command=[
            sys.executable,
            "-c",
            "import pathlib, sys; pathlib.Path(sys.argv[1]).touch()",
            str(stop_file),
        ],
        health_url=None,
        graceful_timeout_seconds=0.3,
    )
    state = lifecycle.start_service(spec, port=port)
    started = time.monotonic()
    try:
        result = lifecycle.stop_service("django", graceful_timeout_seconds=spec.graceful_timeout_seconds)
        stopped_before_cleanup = not process_exists(state.pid)
        port_released_before_cleanup = is_port_available("127.0.0.1", port)
    finally:
        cleanup_file.touch()
        if process_exists(state.pid) and not lifecycle.platform_ops.wait_process_exit(state.pid, 5.0):
            if lifecycle.platform_ops.process_matches_command(state.pid, state.command):
                kill_process(state.pid)
            assert not process_exists(state.pid), "Owned toy process survived cleanup"

    assert time.monotonic() - started >= spec.graceful_timeout_seconds
    assert result.stopped is True
    assert result.reason in {"terminated", "killed"}
    assert result.forced is True
    assert result.force_requested is False
    assert stop_file.exists()
    assert stopped_before_cleanup
    assert port_released_before_cleanup


def real_serve_spec(tmp_path: Path, ports: list[int], stop_file: Path, environment: dict[str, str]) -> ServiceSpec:
    return ServiceSpec.from_values(
        "django",
        ports,
        [
            str(SELECTED_WINDOWS_PYTHON),
            str(ROOT / "manage.py"),
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "{port}",
            "--stop-file",
            str(stop_file),
        ],
        stop_command=[
            str(SELECTED_WINDOWS_PYTHON),
            "-c",
            "import pathlib, sys; pathlib.Path(sys.argv[1]).touch()",
            str(stop_file),
        ],
        cwd=ROOT,
        env=environment,
        health_url="http://{host}:{port}/ai/",
        graceful_timeout_seconds=5.0,
        port_release_timeout_seconds=3.0,
    )


def assert_serve_spec_uses_selected_python(spec: ServiceSpec) -> None:
    assert Path(spec.command[0]).resolve() == SELECTED_WINDOWS_PYTHON
    assert Path(spec.stop_command[0]).resolve() == SELECTED_WINDOWS_PYTHON


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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
