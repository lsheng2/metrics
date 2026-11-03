import os
from pathlib import Path
import subprocess
import sys
import threading
from time import monotonic

import pywintypes
import win32api
import win32con
import win32job

from provider_sync.app.api.access_contracts import AccessError


class PipeCollector:
    def __init__(self, process, limit):
        self.process = process
        self.limit = limit
        self.outputs = [bytearray(), bytearray()]
        self.failed = threading.Event()
        self.threads = []

    def start(self, payload):
        for stream, output in zip((self.process.stdout, self.process.stderr), self.outputs):
            self.threads.append(threading.Thread(target=self.drain, args=(stream, output), daemon=True))
        self.threads.append(threading.Thread(target=self.send, args=(payload,), daemon=True))
        for thread in self.threads:
            thread.start()

    def drain(self, stream, output):
        try:
            while chunk := stream.read(4096):
                if len(output) + len(chunk) > self.limit:
                    self.failed.set()
                    self.process.kill()
                    break
                output.extend(chunk)
        except (OSError, ValueError):
            self.failed.set()
        finally:
            stream.close()

    def send(self, payload):
        try:
            self.process.stdin.write(payload)
            self.process.stdin.close()
        except (OSError, ValueError):
            self.failed.set()

    def join(self, deadline):
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - monotonic()))
        return not any(thread.is_alive() for thread in self.threads)


def run_node(executable, arguments, payload, seconds, *, output_limit=65536):
    if sys.platform != 'win32' or seconds <= 0:
        raise AccessError('SCOPE_UNVERIFIABLE')
    deadline = monotonic() + seconds
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP'}}
    job = process = process_handle = collector = None
    cleanup_ok = True
    try:
        job = win32job.CreateJobObject(None, '')
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info['BasicLimitInformation']['LimitFlags'] = (
            win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | win32job.JOB_OBJECT_LIMIT_JOB_MEMORY)
        info['BasicLimitInformation']['ActiveProcessLimit'] = 1
        info['JobMemoryLimit'] = 256 * 1024**2
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        process = subprocess.Popen(
            [executable, '--max-old-space-size=64', *arguments], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            cwd=str(Path(executable).parent), close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, process.pid)
        win32job.AssignProcessToJobObject(job, process_handle)
        win32api.CloseHandle(process_handle)
        process_handle = None
        collector = PipeCollector(process, output_limit)
        collector.start(payload)
        process.wait(timeout=max(0, deadline - monotonic()))
        if (not collector.join(deadline) or monotonic() > deadline or collector.failed.is_set()
                or process.returncode or collector.outputs[1]):
            raise AccessError('SCOPE_UNVERIFIABLE')
        return bytes(collector.outputs[0])
    except (OSError, ValueError, RuntimeError, pywintypes.error, subprocess.TimeoutExpired):
        raise AccessError('SCOPE_UNVERIFIABLE') from None
    finally:
        cleanup_deadline = monotonic() + 5
        try:
            if job is not None:
                win32job.TerminateJobObject(job, 125)
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=max(0, cleanup_deadline - monotonic()))
                if collector is not None:
                    cleanup_ok = collector.join(cleanup_deadline)
                if cleanup_ok:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()
        except (OSError, ValueError, RuntimeError, pywintypes.error, subprocess.TimeoutExpired):
            cleanup_ok = False
        finally:
            if process_handle is not None:
                win32api.CloseHandle(process_handle)
            if job is not None:
                win32api.CloseHandle(job)
        if not cleanup_ok:
            raise AccessError('SCOPE_UNVERIFIABLE') from None
