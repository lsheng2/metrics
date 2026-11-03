from collections import deque
from dataclasses import dataclass, replace
import importlib
import threading

from django.db import connections

from project_management.app.domain.run_contracts import RunError, RuntimeStopResult
from project_management.app.domain.run_values import NONTERMINAL_STATES


@dataclass(frozen=True, slots=True)
class _RunNotification:
    actor: object
    project_id: str
    stage_id: str
    operation_id: str

    @property
    def key(self):
        return self.project_id, self.stage_id, self.operation_id


class ProjectRunRuntime:
    def __init__(self, run_service, worker):
        self.run_service = run_service
        self.worker = worker
        self.notifier = self.notify
        self._condition = threading.Condition()
        self._pending = deque()
        self._queued_keys = set()
        self._active = None
        self._active_keys = set()
        self._unresolved = set()
        self._thread = None
        self._stopping = threading.Event()
        self._accepting = False

    def start(self):
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self.run_service.reconcile_interrupted()
            self._stopping.clear()
            self._accepting = True
            self.run_service.notifier = self.notifier
            self._thread = threading.Thread(
                target=self._run,
                name='project-run-worker',
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout_seconds):
        if type(timeout_seconds) not in {int, float} or timeout_seconds < 0:
            timeout_seconds = 0
        with self._condition:
            self._accepting = False
            if self.run_service.notifier is self.notifier:
                self.run_service.notifier = None
            pending = tuple(self._pending)
            self._pending.clear()
            self._queued_keys.clear()
            active = self._active
            self._stopping.set()
            self._condition.notify_all()
        for notification in pending:
            if not self._request_cancel(notification):
                self._unresolved.add(notification.operation_id)
        if active is not None:
            if not self._request_cancel(active):
                self._unresolved.add(active.operation_id)
        thread = self._thread
        if thread is not None:
            thread.join(timeout_seconds)
        alive = thread is not None and thread.is_alive()
        active_id = self._active.operation_id if alive and self._active is not None else None
        unresolved = set(self._unresolved)
        if active_id is not None:
            unresolved.add(active_id)
        return RuntimeStopResult(not alive, active_id, tuple(sorted(unresolved)))

    def notify(self, actor, project_id, stage_id, operation_id):
        notification = _RunNotification(actor, str(project_id), str(stage_id), str(operation_id))
        with self._condition:
            if not self._accepting:
                raise RunError('RUN_UNAVAILABLE')
            if notification.key in self._queued_keys or notification.key in self._active_keys:
                return
            if len(self._pending) >= self.run_service.policy.max_queued_operations:
                return
            self._pending.append(notification)
            self._queued_keys.add(notification.key)
            self._condition.notify()

    def _run(self):
        try:
            while True:
                notification = self._next_notification()
                if notification is None:
                    return
                try:
                    self.worker.execute(
                        notification.actor,
                        notification.project_id,
                        notification.stage_id,
                        notification.operation_id,
                    )
                except Exception:
                    self._fail_operation(notification)
                finally:
                    with self._condition:
                        self._active_keys.discard(notification.key)
                        if self._active == notification:
                            self._active = None
                        self._condition.notify_all()
        finally:
            connections.close_all()

    def _next_notification(self):
        with self._condition:
            while not self._pending:
                if self._stopping.is_set():
                    return None
                self._condition.wait(timeout=0.2)
            notification = self._pending.popleft()
            self._queued_keys.discard(notification.key)
            self._active = notification
            self._active_keys.add(notification.key)
            return notification

    def _request_cancel(self, notification):
        try:
            operation = self.run_service.get(
                notification.actor,
                notification.project_id,
                notification.stage_id,
                notification.operation_id,
            )
            if operation.state in NONTERMINAL_STATES:
                self.run_service.cancel(
                    notification.actor,
                    notification.project_id,
                    notification.stage_id,
                    notification.operation_id,
                    expected_revision=operation.revision,
                )
            return True
        except Exception:
            return False

    def _fail_operation(self, notification):
        try:
            operation = self.run_service.get(
                notification.actor,
                notification.project_id,
                notification.stage_id,
                notification.operation_id,
            )
            if operation.state not in NONTERMINAL_STATES:
                return
            self.run_service.transition(
                notification.actor,
                notification.project_id,
                notification.stage_id,
                notification.operation_id,
                lambda current: replace(
                    current,
                    state='failed',
                    revision=current.revision + 1,
                    error_code='RUN_INTERRUPTED',
                ),
            )
        except Exception:
            return


_INSTALLED_RUNTIME = None
_REGISTRY_LOCK = threading.Lock()


def install_project_runtime(runtime):
    global _INSTALLED_RUNTIME
    with _REGISTRY_LOCK:
        if _INSTALLED_RUNTIME is not None and _INSTALLED_RUNTIME is not runtime:
            raise RunError('RUN_BUSY')
        _INSTALLED_RUNTIME = runtime
        return runtime


def get_project_runtime():
    with _REGISTRY_LOCK:
        return _INSTALLED_RUNTIME


def clear_project_runtime(runtime):
    global _INSTALLED_RUNTIME
    with _REGISTRY_LOCK:
        if _INSTALLED_RUNTIME is runtime:
            _INSTALLED_RUNTIME = None


def build_project_runtime():
    return importlib.import_module('project_management.app.api.run_factories').build_project_runtime()


def build_run_read_service():
    return importlib.import_module('project_management.app.api.run_factories').build_run_read_service()
