import os
import threading
import time

from ai_host.settings import (
    HOST_ACTIVE_WATCHDOG_SECONDS,
    HOST_DRAIN_SECONDS,
    HOST_FINAL_WATCHDOG_SECONDS,
    HOST_FLUSH_SECONDS,
    HOST_SERVER_STOP_SECONDS,
    HOST_WATCHDOG_SECONDS,
    HOST_WAIT_SLICE_SECONDS,
    HOST_WATCHDOG_OUTPUT_SECONDS,
    HTTP_CLOSE_TIMEOUT_SECONDS,
)


class StopBudget:
    """Absolute host deadlines; project completion may only tighten the final stage."""

    def __init__(self, *, started_at=None):
        self.started_at = time.monotonic() if started_at is None else started_at
        self.http_close_deadline = self.started_at + HTTP_CLOSE_TIMEOUT_SECONDS
        self.drain_deadline = self.started_at + HOST_DRAIN_SECONDS
        self.flush_deadline = self.started_at + HOST_FLUSH_SECONDS
        self.server_deadline = self.started_at + HOST_SERVER_STOP_SECONDS
        self.changed = threading.Condition()
        self._watchdog_deadline = self.started_at + HOST_WATCHDOG_SECONDS

    @property
    def watchdog_deadline(self):
        with self.changed:
            return self._watchdog_deadline

    def project_requested(self, *, active):
        if active:
            with self.changed:
                self._watchdog_deadline = self.started_at + HOST_ACTIVE_WATCHDOG_SECONDS
                self.changed.notify_all()

    def project_returned(self, *, at=None):
        returned_at = time.monotonic() if at is None else at
        with self.changed:
            self._watchdog_deadline = min(
                self._watchdog_deadline, returned_at + HOST_FINAL_WATCHDOG_SECONDS,
            )
            self.changed.notify_all()


def bounded_output_exit(code, write_output, *, exit_process=os._exit):
    def output():
        try:
            write_output()
        except Exception:
            pass

    writer = threading.Thread(target=output, name='serve-emergency-output', daemon=True)
    writer.start()
    writer.join(HOST_WATCHDOG_OUTPUT_SECONDS)
    exit_process(code)


def start_watchdog(budget, *, write_output, exit_process=os._exit):
    def watch():
        with budget.changed:
            while True:
                remaining = budget.watchdog_deadline - time.monotonic()
                if remaining <= 0:
                    break
                budget.changed.wait(min(HOST_WAIT_SLICE_SECONDS, remaining))
        bounded_output_exit(3, write_output, exit_process=exit_process)

    watcher = threading.Thread(target=watch, name='serve-stop-watchdog', daemon=True)
    watcher.start()
    return watcher


def start_stop_monitor(stop_event, stop_file, deadline):
    if stop_file is None and deadline is None:
        return None

    def watch():
        while not stop_event.is_set():
            if ((stop_file is not None and stop_file.exists())
                    or (deadline is not None and time.monotonic() >= deadline)):
                stop_event.set()
                return
            stop_event.wait(0.1)

    monitor = threading.Thread(target=watch, name='serve-stop-monitor', daemon=True)
    monitor.start()
    return monitor
