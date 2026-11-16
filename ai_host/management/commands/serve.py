import errno
import json
import math
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import SystemCheckError
from project_management.app.api.task_runtime import LocalRuntimeCleanupError


class Command(BaseCommand):
    help = 'Serve Metrics Django and the embedded AI runtime from one process.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--host', default='127.0.0.1')
        parser.add_argument('--port', type=int, required=True)
        parser.add_argument('--stop-file')
        parser.add_argument('--lifetime-seconds', type=float)

    def handle(self, *args, **options):
        try:
            options = dict(options)
            options['stop_file'] = self._stop_file(options.get('stop_file'))
            options['lifetime_seconds'] = self._lifetime(options.get('lifetime_seconds'))
        except ValueError as error:
            raise SystemExit(str(error)) from None
        try:
            listener = self._bind_listener(options['host'], options['port'])
        except OSError:
            self.stdout.write('serve bind failed.')
            self._exit(1)
            return
        try:
            code = self._run_bound_server(listener, options)
        except SystemCheckError:
            listener.close()
            self.stdout.write('serve startup failed (system_check_failed).')
            self._exit(1)
            return
        except Exception as error:
            listener.close()
            self.stdout.write(f'serve startup failed ({self._error_code(error)}).')
            self._exit(3 if isinstance(error, LocalRuntimeCleanupError) else 1)
            return
        self._exit(code)

    def _bind_listener(self, host, port):
        family = socket.AF_INET6 if host == '::1' else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        try:
            if sys.platform.startswith('win') and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            elif hasattr(socket, 'SO_REUSEADDR'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.setblocking(False)
            return listener
        except OSError:
            listener.close()
            raise

    def _run_bound_server(self, listener, options):
        self.check()

        from django.core.handlers.wsgi import WSGIHandler
        from waitress import create_server
        from ai_host.admission import admit_runtime_candidate
        admit_runtime_candidate()

        from ai_base_runtime import start_blocking
        from ai_host.host import MetricsHost
        from ai_host.lifecycle import stop_owned_resources
        from ai_host.package import METRICS_APP
        from ai_host.principals import task_principal
        from ai_host.task_runs import RuntimeTaskRunPort
        from ai_host.settings import (
            RUNTIME_START_SECONDS,
            SERVER_THREADS,
            body_limit_for_waitress,
            build_runtime_settings,
        )
        from ai_host.state import attach, detach
        from ai_host.wiring import build_wsgi_application
        from project_management.app.domain.run_contracts import RunError
        from project_management.runtime import build_project_runtime, clear_project_runtime, install_project_runtime

        stop_event = threading.Event()
        stop_file = options.get('stop_file')
        lifetime_seconds = options.get('lifetime_seconds')
        deadline = None if lifetime_seconds is None else time.monotonic() + lifetime_seconds
        runtime_settings = build_runtime_settings()
        host = MetricsHost()
        host.config.state_dir.mkdir(parents=True, exist_ok=True)
        max_request_body_size = body_limit_for_waitress((METRICS_APP,))
        context = start_blocking(
            runtime_settings,
            host,
            [METRICS_APP],
            start_timeout=RUNTIME_START_SECONDS,
        )
        server = None
        server_thread = None
        handle = None
        project_runtime = None
        installed_project_runtime = False
        outcome = None
        old_handlers = {}
        try:
            old_handlers = self._install_signal_handlers(stop_event)
            with context as handle:
                attach(handle)
                try:
                    try:
                        candidate_runtime = build_project_runtime(
                            task_runs=RuntimeTaskRunPort(handle.blocking.task_runs),
                            principal_resolver=task_principal,
                        )
                    except RunError as error:
                        if error.code != 'RUN_UNAVAILABLE':
                            raise
                    else:
                        project_runtime = install_project_runtime(candidate_runtime)
                        installed_project_runtime = True
                        project_runtime.start()
                    django_app = WSGIHandler()
                    app = build_wsgi_application(
                        django_app,
                        handle.wsgi_app(),
                        is_accepting_requests=lambda: not stop_event.is_set(),
                    )
                    server = create_server(
                        app,
                        sockets=[listener],
                        threads=SERVER_THREADS,
                        channel_request_lookahead=1,
                        max_request_body_size=max_request_body_size,
                    )
                    server_thread = threading.Thread(target=server.run, name='serve-http', daemon=False)
                    server_thread.start()
                    self._wait_for_stop(stop_event, stop_file, deadline)
                finally:
                    outcome = stop_owned_resources(
                        handle=handle,
                        server=server,
                        server_thread=server_thread,
                        project_runtime=project_runtime if installed_project_runtime else None,
                    )
            outcome = self._with_runtime_stop_result(outcome, handle.stop_result)
            return outcome.exit_code
        except BaseException:
            failure = context.startup_failure
            if failure is not None and not failure.rollback_result.completed:
                raise LocalRuntimeCleanupError() from None
            if outcome is not None and handle is not None:
                outcome = self._with_runtime_stop_result(outcome, handle.stop_result)
                if outcome.exit_code == 3:
                    raise LocalRuntimeCleanupError() from None
            raise
        finally:
            if installed_project_runtime and project_runtime is not None:
                clear_project_runtime(project_runtime)
            if handle is not None:
                detach(handle)
            self._restore_signal_handlers(old_handlers)
            if outcome is not None:
                self._write_stop_event(outcome.project_result)

    def _wait_for_stop(self, stop_event, stop_file, deadline):
        while not stop_event.is_set():
            if stop_file is not None and stop_file.exists():
                stop_event.set()
                return
            if deadline is not None and time.monotonic() >= deadline:
                stop_event.set()
                return
            time.sleep(0.1)

    def _write_stop_event(self, result):
        if result is None:
            self.stdout.write(json.dumps({
                'schema_version': 1,
                'event': 'project_runtime_absent',
            }, separators=(',', ':')))
            return
        self.stdout.write(json.dumps({
            'schema_version': 1,
            'event': 'project_runtime_stopped',
            'stopped': bool(result.stopped),
            'active_operation_id': result.active_operation_id,
            'unresolved': list(result.unresolved),
        }, separators=(',', ':')))

    def _with_runtime_stop_result(self, outcome, stop_result):
        if stop_result is not None and stop_result.completed:
            return outcome
        from ai_host.lifecycle import StopOutcome
        errors = tuple(dict.fromkeys(outcome.cleanup_errors + ('runtime_stop_incomplete',)))
        return StopOutcome(
            exit_code=3,
            project_result=outcome.project_result,
            http_result=outcome.http_result,
            runtime_result=stop_result,
            cleanup_errors=errors,
        )

    def _install_signal_handlers(self, stop_event):
        handlers = {}

        def handler(signum, frame):
            if stop_event.is_set():
                self.stdout.write('serve forced exit.')
                self._exit(130)
            stop_event.set()

        for signum in self._signal_numbers():
            try:
                handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, handler)
            except (OSError, ValueError):
                continue
        return handlers

    def _restore_signal_handlers(self, handlers):
        for signum, handler in handlers.items():
            try:
                signal.signal(signum, handler)
            except (OSError, ValueError):
                continue

    def _signal_numbers(self):
        numbers = [signal.SIGINT, signal.SIGTERM]
        sigbreak = getattr(signal, 'SIGBREAK', None)
        if sigbreak is not None:
            numbers.append(sigbreak)
        return numbers

    def _stop_file(self, value):
        if value in (None, ''):
            return None
        path = Path(value)
        if not path.is_absolute():
            raise ValueError('--stop-file must be absolute')
        return path

    def _lifetime(self, value):
        if value is None:
            return None
        if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
            raise ValueError('--lifetime-seconds must be positive')
        return float(value)

    def _error_code(self, error):
        code = getattr(error, 'code', None)
        if isinstance(code, str) and code:
            return code
        return error.__class__.__name__.lower()

    def _exit(self, code):
        if code in {3, 130}:
            self.stdout.flush()
            self.stderr.flush()
            os._exit(code)
        raise SystemExit(code)
