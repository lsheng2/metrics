from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from service_lifecycle_engine import platform_ops
else:
    from . import platform_ops


CTRL_BREAK_EVENT = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a targeted graceful stop signal to an owned process.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expected-start-marker", default="")
    parser.add_argument("--expected-command-line", default="")
    parser.add_argument("--event", choices=("ctrl-break", "sigterm"), default="ctrl-break")
    args = parser.parse_args(argv)
    result = controlled_stop(
        args.pid,
        expected_start_marker=args.expected_start_marker,
        expected_command_line=args.expected_command_line,
        event=args.event,
    )
    print(json.dumps(result, sort_keys=True))
    return int(result["exit_code"])


def controlled_stop(
    pid: int,
    *,
    expected_start_marker: str = "",
    expected_command_line: str = "",
    event: str = "ctrl-break",
) -> dict[str, object]:
    if pid <= 0:
        return result("invalid_pid", 2, pid=pid)
    if not expected_start_marker.strip() or not expected_command_line.strip():
        return result("missing_identity", 2, pid=pid)
    if not platform_ops.process_exists(pid):
        return result("not_running", 0, pid=pid)
    current_start_marker = platform_ops.process_start_marker(pid)
    if expected_start_marker and current_start_marker != expected_start_marker:
        return result("identity_mismatch", 3, pid=pid, observed_start_marker=current_start_marker)
    current_command_line = platform_ops.get_process_command_line(pid)
    if expected_command_line and current_command_line != expected_command_line:
        return result("identity_mismatch", 3, pid=pid, observed_command_line=current_command_line)
    sent = send_control_event(pid, event)
    if sent["sent"]:
        return result("signal_sent", 0, pid=pid, **sent)
    return result("signal_failed", 4, pid=pid, **sent)


def send_control_event(pid: int, event: str) -> dict[str, object]:
    if sys.platform == "win32":
        if event != "ctrl-break":
            return {"sent": False, "error": "unsupported_event"}
        return send_windows_control_event(pid, CTRL_BREAK_EVENT)
    if event != "sigterm":
        return {"sent": False, "error": "unsupported_event"}
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as error:
        return {"sent": False, "error": type(error).__name__}
    return {"sent": True, "event": "sigterm"}


def send_windows_control_event(pid: int, event: int) -> dict[str, object]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    ignore_handler = handler_type(lambda control_event: True)
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(int(pid)):
        return {"sent": False, "event": "ctrl-break", "winerror": ctypes.get_last_error(), "phase": "attach"}
    kernel32.SetConsoleCtrlHandler(ignore_handler, True)
    try:
        ok = bool(kernel32.GenerateConsoleCtrlEvent(int(event), int(pid)))
        winerror = ctypes.get_last_error()
        time.sleep(0.2)
        return {"sent": ok, "event": "ctrl-break", "winerror": winerror, "phase": "send"}
    finally:
        kernel32.FreeConsole()


def result(reason: str, exit_code: int, **fields: object) -> dict[str, object]:
    return {"schema_version": 1, "reason": reason, "exit_code": exit_code, **fields}


if __name__ == "__main__":
    raise SystemExit(main())
