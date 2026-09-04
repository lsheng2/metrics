from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import PlatformOperationSet
from service_lifecycle_engine import platform_ops


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
