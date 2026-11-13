from __future__ import annotations

import gc
import os
import subprocess
import sys
import time
import weakref
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import PlatformOperationSet
from service_lifecycle_engine import platform_ops

LAUNCHER_SCRIPT = """
import os, subprocess, sys
sys.path.insert(0, sys.argv[1])
from service_lifecycle_engine import platform_ops
child = platform_ops.start_process(
    (sys.executable, "-c", "import time; time.sleep(30)"),
    sys.argv[2],
    dict(os.environ),
    subprocess.DEVNULL,
    subprocess.DEVNULL,
    platform_ops.creation_flags(),
)
print(child.pid, flush=True)
"""


def test_shouldAllowFakePlatformOpsToProveRegisteredProcessOwnership():
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 12345,
        process_matches_command=lambda pid, command: pid == 12345 and command == ("python", "api.py"),
    )

    assert operations.registered_process_is_owned(12345, ("python", "api.py"))


def test_shouldAllowFakePlatformOpsToDenyUnmatchedRegisteredProcessOwnership():
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: False,
    )

    assert not operations.registered_process_is_owned(12345, ("python", "api.py"))


def test_shouldAllowFakePlatformOpsToResolveListenerOwnershipByProcessGroup():
    operations = PlatformOperationSet(
        get_listening_process_ids=lambda host, port: (222,),
        process_group_id=lambda pid: 7 if pid in {111, 222} else 8,
    )

    assert operations.owned_listener_pids("127.0.0.1", 8100, wrapper_pid=111) == (222,)


def test_shouldDenyListenerOwnershipWhenProcessGroupDoesNotMatch():
    operations = PlatformOperationSet(
        get_listening_process_ids=lambda host, port: (222,),
        process_group_id=lambda pid: 7 if pid == 111 else 8,
    )

    assert operations.owned_listener_pids("127.0.0.1", 8100, wrapper_pid=111) == ()


def test_processMatchesCommandShouldRejectSubstringOnlyArgumentMatch(monkeypatch):
    monkeypatch.setattr(platform_ops, "get_process_command_line", lambda pid: "python unrelated-api.py --serve-old-api.py")

    assert not platform_ops.process_matches_command(12345, ("python", "api.py"))


def test_processMatchesCommandShouldAcceptExactTokenizedCommand(monkeypatch):
    python_executable = str(Path(sys.executable))
    monkeypatch.setattr(platform_ops, "get_process_command_line", lambda pid: f'"{python_executable}" manage.py runserver 127.0.0.1:8002 --noreload')

    assert platform_ops.process_matches_command(12345, (python_executable, "manage.py", "runserver", "127.0.0.1:8002", "--noreload"))


def test_processMatchesCommandShouldRejectSameBasenameDifferentQualifiedExecutable(monkeypatch):
    expected = str(Path("C:/expected/python.exe"))
    monkeypatch.setattr(platform_ops, "get_process_command_line", lambda pid: '"C:/other/python.exe" manage.py runserver 127.0.0.1:8002 --noreload')

    assert not platform_ops.process_matches_command(12345, (expected, "manage.py", "runserver", "127.0.0.1:8002", "--noreload"))


def test_processMatchesCommandShouldRejectUnqualifiedActualForRelativeQualifiedExpected(monkeypatch):
    monkeypatch.setattr(platform_ops, "get_process_command_line", lambda pid: "python.exe manage.py runserver 127.0.0.1:8002 --noreload")

    assert not platform_ops.process_matches_command(12345, ("./python.exe", "manage.py", "runserver", "127.0.0.1:8002", "--noreload"))


def test_processMatchesCommandShouldAllowBasenameFallbackForUnqualifiedExecutable(monkeypatch):
    monkeypatch.setattr(platform_ops, "get_process_command_line", lambda pid: '"C:/other/python.exe" manage.py runserver 127.0.0.1:8002 --noreload')

    assert platform_ops.process_matches_command(12345, ("python.exe", "manage.py", "runserver", "127.0.0.1:8002", "--noreload"))


def test_processExistsShouldReapExitedChildAfterCallerDropsHandle(tmp_path):
    process = start_child(tmp_path, "pass")
    pid = process.pid
    handle = weakref.ref(process)
    del process

    assert wait_until(lambda: not platform_ops.process_exists(pid))
    gc.collect()
    assert handle() is None


def test_waitProcessExitShouldReapKilledChildAfterCallerDropsHandle(tmp_path):
    process = start_child(tmp_path, "import time; time.sleep(30)")
    pid = process.pid
    handle = weakref.ref(process)
    del process

    platform_ops.kill_process(pid)

    assert platform_ops.wait_process_exit(pid, 10.0)
    gc.collect()
    assert handle() is None


def test_processExistsShouldUseOsCheckWhenExitCodeWasCollectedElsewhere(monkeypatch, tmp_path):
    process = start_child(tmp_path, "pass")
    process.wait(timeout=10)
    if sys.platform == "win32":
        monkeypatch.setattr(platform_ops, "process_exists_windows", lambda pid: True)
    else:
        monkeypatch.setattr(platform_ops.os, "kill", lambda pid, signal_number: None)

    assert platform_ops.process_exists(process.pid)


def test_startProcessShouldLeaveChildRunningWhenLauncherExits(tmp_path):
    launcher = subprocess.run(
        [sys.executable, "-c", LAUNCHER_SCRIPT, str(ROOT / "scripts"), str(tmp_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    child_pid = int(launcher.stdout.strip())
    child_was_running = platform_ops.process_exists(child_pid)
    platform_ops.kill_process(child_pid)

    assert child_was_running
    assert platform_ops.wait_process_exit(child_pid, 10.0)


def start_child(tmp_path: Path, code: str):
    return platform_ops.start_process(
        (sys.executable, "-c", code),
        str(tmp_path),
        dict(os.environ),
        subprocess.DEVNULL,
        subprocess.DEVNULL,
        platform_ops.creation_flags(),
    )


def wait_until(condition, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()
