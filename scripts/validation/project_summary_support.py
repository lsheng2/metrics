from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys


def worker_record_matches(record, worker_pid, launcher_pid, command):
    try:
        actual = [part.strip('"').casefold() for part in shlex.split(record['CommandLine'], posix=False)]
        expected = [str(part).strip('"').casefold() for part in command]
        image = record['ExecutablePath'].replace('\\', '/').rsplit('/', 1)[-1].lower()
        return (
            record['ProcessId'] == worker_pid
            and record['ParentProcessId'] == launcher_pid
            and image == 'python.exe'
            and actual[1:] == expected[1:]
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def worker_matches_process(worker_pid, process):
    if sys.platform != 'win32' or process.poll() is not None:
        return False
    script = (
        '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()\n'
        f'Get-CimInstance Win32_Process -Filter "ProcessId={int(worker_pid)}" | '
        'Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress'
    )
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True,
            encoding='utf-8',
            check=True,
            timeout=10,
        )
        record = json.loads(result.stdout)
        return worker_record_matches(record, worker_pid, process.pid, process.args)
    except (subprocess.SubprocessError, ValueError):
        return False
