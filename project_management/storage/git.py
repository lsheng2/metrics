from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from project_management.app.domain.captures import ArchiveError


ATTRIBUTES = b'* -text -filter\n'
OPTIONS = {
    'core.autocrlf': 'false',
    'core.fsmonitor': 'false',
    'core.untrackedCache': 'false',
    'core.attributesFile': os.devnull,
    'commit.gpgSign': 'false',
    'gc.auto': '0',
    'maintenance.auto': 'false',
    'core.longpaths': 'true',
    'advice.detachedHead': 'false',
}


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: bytes
    stderr: bytes = b''


def git_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    environment.update({
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_TERMINAL_PROMPT': '0',
        'GIT_NO_REPLACE_OBJECTS': '1',
        'LC_ALL': 'C',
    })
    if extra:
        environment.update(extra)
    return environment


class GitRunner:
    def __init__(self, root: Path, hooks: Path, *, timeout: float = 30, output_limit: int = 16 * 1024 * 1024):
        self.root = root
        self.hooks = hooks
        self.timeout = timeout
        self.output_limit = output_limit
        self.executable = shutil.which('git')
        if self.executable is None:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')

    def run(
        self,
        arguments: list[str],
        *,
        check: bool = True,
        input_data: bytes | None = None,
        extra_env: dict[str, str] | None = None,
        output_limit: int | None = None,
        output_limit_code: str = 'ARCHIVE_STORAGE_UNAVAILABLE',
        timeout: float | None = None,
    ) -> GitResult:
        effective_output_limit = self.output_limit if output_limit is None else output_limit
        command = [self.executable, '-C', str(self.root)]
        for key, value in {**OPTIONS, 'core.hooksPath': str(self.hooks)}.items():
            command.extend(['-c', f'{key}={value}'])
        try:
            process = subprocess.Popen(
                [*command, *arguments],
                env=git_environment(extra_env),
                stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
        outputs = [bytearray(), bytearray()]
        exceeded = threading.Event()
        failed = threading.Event()
        threads = [
            threading.Thread(target=self._drain, args=(stream, destination, exceeded, effective_output_limit), daemon=True)
            for stream, destination in zip((process.stdout, process.stderr), outputs)
        ]
        if input_data is not None:
            threads.append(threading.Thread(target=self._send, args=(process.stdin, input_data, failed), daemon=True))
        for thread in threads:
            thread.start()
        timed_out = self._wait(process, exceeded, timeout)
        for thread in threads:
            thread.join(timeout=5)
        if exceeded.is_set():
            raise ArchiveError(output_limit_code)
        if timed_out or failed.is_set() or any(thread.is_alive() for thread in threads):
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        if check and process.returncode:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return GitResult(process.returncode, bytes(outputs[0]), bytes(outputs[1]))

    def _send(self, stream, data, failed):
        try:
            stream.write(data)
        except OSError:
            failed.set()
        finally:
            try:
                stream.close()
            except OSError:
                failed.set()

    def _drain(self, stream, destination: bytearray, exceeded: threading.Event, output_limit: int) -> None:
        try:
            while chunk := stream.read(65536):
                if len(destination) + len(chunk) > output_limit:
                    exceeded.set()
                    return
                destination.extend(chunk)
        finally:
            stream.close()

    def _wait(self, process, exceeded: threading.Event, timeout=None) -> bool:
        deadline = time.monotonic() + (self.timeout if timeout is None else min(self.timeout, timeout))
        timed_out = False
        try:
            while process.poll() is None:
                if exceeded.is_set() or time.monotonic() >= deadline:
                    timed_out = not exceeded.is_set()
                    process.kill()
                    break
                try:
                    process.wait(timeout=min(0.01, max(0, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        return timed_out
