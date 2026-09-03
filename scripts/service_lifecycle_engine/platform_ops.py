from __future__ import annotations

import hashlib
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

if sys.platform == "win32":
    import ctypes


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex((host, port)) == 0:
            return False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def http_status_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def http_probe(url: str, timeout: float = 1.0, body_limit: int = 2048) -> dict[str, object]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(body_limit)
            return {
                "reachable": True,
                "status": response.status,
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_preview": body.decode("utf-8", errors="replace")[:200],
            }
    except (OSError, urllib.error.URLError) as error:
        return {"reachable": False, "error": type(error).__name__}


def wait_port_available(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_port_available(host, port):
            return True
        time.sleep(0.05)
    return is_port_available(host, port)


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return process_exists_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def process_matches_command(pid: int, expected_command: tuple[str, ...]) -> bool:
    command_line = get_process_command_line(pid)
    if not command_line or not expected_command:
        return False
    actual = command_line.casefold() if sys.platform == "win32" else command_line
    expected_parts = [part.casefold() if sys.platform == "win32" else part for part in expected_command]
    executable = expected_parts[0]
    executable_name = os.path.basename(executable)
    if executable not in actual and executable_name not in actual:
        return False
    return all(part in actual for part in expected_parts[1:])


def get_process_command_line(pid: int) -> str:
    if pid <= 0:
        return ""
    if sys.platform == "win32":
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\").CommandLine",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return completed.stdout.strip()
    proc_cmdline = f"/proc/{int(pid)}/cmdline"
    try:
        with open(proc_cmdline, "rb") as proc_file:
            return proc_file.read().replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    except OSError:
        completed = subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return completed.stdout.strip()


def process_exists_windows(pid: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def terminate_process(pid: int) -> None:
    if sys.platform == "win32":
        terminate_process_tree_windows(pid, force=False)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def kill_process(pid: int) -> None:
    if sys.platform == "win32":
        terminate_process_tree_windows(pid, force=True)
        return
    kill_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    try:
        os.kill(pid, kill_signal)
    except ProcessLookupError:
        pass


def terminate_process_windows(pid: int) -> None:
    process_terminate = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(process_terminate, False, int(pid))
    if not handle:
        return
    try:
        ctypes.windll.kernel32.TerminateProcess(handle, 1)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def terminate_process_tree_windows(pid: int, force: bool) -> None:
    command = ["taskkill", "/PID", str(int(pid)), "/T"]
    if force:
        command.append("/F")
    completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if completed.returncode != 0 and force:
        terminate_process_windows(pid)


def wait_process_exit(pid: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not process_exists(pid):
            return True
        time.sleep(0.05)
    return not process_exists(pid)


def creation_flags() -> int:
    return subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0


def get_listening_process_ids(host: str, port: int) -> tuple[int, ...]:
    if sys.platform == "win32":
        return get_listening_process_ids_windows(port)
    return get_listening_process_ids_posix(port)


def get_listening_process_ids_windows(port: int) -> tuple[int, ...]:
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    process_ids: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        local_address = parts[1]
        if local_address.endswith(f":{port}"):
            process_ids.add(int(parts[-1]))
    return tuple(sorted(process_ids))


def get_listening_process_ids_posix(port: int) -> tuple[int, ...]:
    lsof = shutil_which("lsof")
    if lsof:
        completed = subprocess.run(
            [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        process_ids = {int(line.strip()) for line in completed.stdout.splitlines() if line.strip().isdigit()}
        if process_ids:
            return tuple(sorted(process_ids))

    ss = shutil_which("ss")
    if ss:
        completed = subprocess.run(
            [ss, "-ltnp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        process_ids: set[int] = set()
        for line in completed.stdout.splitlines():
            if f":{port} " not in line and f":{port}\t" not in line:
                continue
            process_ids.update(int(match) for match in re.findall(r"pid=(\d+)", line))
        return tuple(sorted(process_ids))

    return ()


def shutil_which(command: str) -> str | None:
    path = os.environ.get("PATH", "")
    executable_extensions = os.environ.get("PATHEXT", "").split(os.pathsep) if sys.platform == "win32" else [""]
    for directory in path.split(os.pathsep):
        for extension in executable_extensions:
            candidate = os.path.join(directory, command + extension)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None
