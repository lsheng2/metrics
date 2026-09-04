from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from . import platform_ops


@dataclass(frozen=True, slots=True)
class PlatformOperationSet:
    is_port_available: Callable[[str, int], bool] = platform_ops.is_port_available
    process_exists: Callable[[int], bool] = platform_ops.process_exists
    process_matches_command: Callable[[int, tuple[str, ...]], bool] = platform_ops.process_matches_command
    process_command_line: Callable[[int], str] = platform_ops.get_process_command_line
    process_start_marker: Callable[[int], str] = platform_ops.process_start_marker
    get_listening_process_ids: Callable[[str, int], Sequence[int]] = platform_ops.get_listening_process_ids
    process_group_id: Callable[[int], int | None] = lambda pid: None
    http_status_ok: Callable[[str], bool] = platform_ops.http_status_ok
    http_probe: Callable[[str], dict[str, object]] = platform_ops.http_probe
    start_process: Callable[..., object] = platform_ops.start_process
    run_command: Callable[[tuple[str, ...], object], None] = platform_ops.run_command
    terminate_process: Callable[[int], None] = platform_ops.terminate_process
    kill_process: Callable[[int], None] = platform_ops.kill_process
    wait_process_exit: Callable[[int, float], bool] = platform_ops.wait_process_exit
    wait_port_available: Callable[[str, int, float], bool] = platform_ops.wait_port_available
    creation_flags: Callable[[], int] = platform_ops.creation_flags

    def registered_process_is_owned(self, pid: int, command: tuple[str, ...]) -> bool:
        return self.process_exists(pid) and self.process_matches_command(pid, command)

    def owned_listener_pids(self, host: str, port: int, wrapper_pid: int) -> tuple[int, ...]:
        wrapper_group_id = self.process_group_id(wrapper_pid)
        if wrapper_group_id is None:
            return ()
        owned_pids = []
        for pid in self.get_listening_process_ids(host, port):
            if self.process_group_id(int(pid)) == wrapper_group_id:
                owned_pids.append(int(pid))
        return tuple(sorted(set(owned_pids)))
