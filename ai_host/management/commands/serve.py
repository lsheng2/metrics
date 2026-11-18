import ipaddress
import json
import math
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
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
        self._stop_event = threading.Event()
        self._startup_failure_code = None
        self._install_signal_handlers(self._stop_event)
        try:
            options = dict(options)
            options['stop_file'] = self._stop_file(options.get('stop_file'))
            options['lifetime_seconds'] = self._lifetime(options.get('lifetime_seconds'))
        except ValueError:
            self._exit(1, message='serve startup failed (configuration_invalid).')
            return
        try:
            listener = self._bind_listener(options['host'], options['port'])
        except OSError:
            self._exit(1, message='serve bind failed.')
            return
        except CommandError:
            self._exit(1, message='serve startup failed (configuration_invalid).')
            return
        try:
            code = self._run_bound_server(listener, options)
        except SystemCheckError:
            listener.close()
            self._exit(1, message='serve startup failed (system_check_failed).')
            return
        except Exception as error:
            listener.close()
            self._exit(
                3 if isinstance(error, LocalRuntimeCleanupError) else 1,
                message=f'serve startup failed ({self._startup_failure_code or self._error_code(error)}).',
            )
            return
        self._exit(code)

    def _bind_listener(self, host, port):
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        loopback = host == 'localhost' or (address is not None and address.is_loopback)
        if not loopback:
            if getattr(django_settings, 'AI_HOST_ALLOW_ANONYMOUS_APPROVAL', False):
                raise CommandError('Non-loopback binding with anonymous approval is prohibited.')
            if django_settings.METRICS_BASIC_AUTH_USERS is None:
                self.stdout.write(json.dumps({'event': 'serve_anonymous_network_bind', 'host': host}))
        family = socket.AF_INET6 if address is not None and address.version == 6 else socket.AF_INET
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
        from ai_host.state import begin_start
        begin_start()
        self.check()

        from django.core.handlers.wsgi import WSGIHandler
        from waitress import create_server
        from ai_host.admission import admit_runtime_candidate
        runtime_record = admit_runtime_candidate()

        from ai_base_runtime import start_blocking
        from ai_host.host import MetricsHost
        from ai_host.lifecycle import run_http_server, stop_owned_resources
        from ai_host.serve_control import start_stop_monitor
        from ai_host.package import METRICS_APP
        from ai_host.principals import task_principal
        from ai_host.task_runs import RuntimeTaskRunPort, admission_metadata_from_host_config
        from ai_host.settings import (
            RUNTIME_START_SECONDS,
            SERVER_THREADS,
            body_limit_for_waitress,
            build_runtime_settings,
        )
        from ai_host.state import attach, begin_stop, detach, record_startup_failure, record_stop
        from ai_host.wiring import build_wsgi_application
        from project_management.app.domain.run_contracts import RunError
        from project_management.runtime import build_project_runtime, clear_project_runtime, install_project_runtime

        stop_event = getattr(self, '_stop_event', None) or threading.Event()
        stop_file = options.get('stop_file')
        lifetime_seconds = options.get('lifetime_seconds')
        deadline = None if lifetime_seconds is None else time.monotonic() + lifetime_seconds
        runtime_settings = build_runtime_settings()
        host = MetricsHost()
        host.config.state_dir.mkdir(parents=True, exist_ok=True)
        max_request_body_size = body_limit_for_waitress(runtime_settings, (METRICS_APP,))
        context = start_blocking(
            runtime_settings,
            host,
            [METRICS_APP],
            start_timeout=RUNTIME_START_SECONDS,
        )
        server = None
        server_thread = None
        server_errors = []
        app = None
        handle = None
        project_runtime = None
        installed_project_runtime = False
        outcome = None
        runtime_failure = None
        try:
            self._install_signal_handlers(stop_event)
            start_stop_monitor(stop_event, stop_file, deadline)
            with context as handle:
                attach(handle)
                try:
                    try:
                        candidate_runtime = build_project_runtime(
                            task_runs=RuntimeTaskRunPort(
                                handle.blocking.task_runs,
                                admission_metadata=admission_metadata_from_host_config(
                                    host.config, runtime_record['version'],
                                ),
                            ),
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
                    server_thread = threading.Thread(
                        target=run_http_server, args=(server, server_errors), name='serve-http', daemon=False,
                    )
                    server_thread.start()
                    runtime_failure = self._wait_for_stop(stop_event, stop_file, deadline, handle)
                finally:
                    stop_event.set()
                    budget = self._begin_stop_budget()
                    begin_stop(handle)
                    outcome = stop_owned_resources(
                        handle=handle,
                        server=server,
                        server_thread=server_thread,
                        project_runtime=project_runtime if installed_project_runtime else None,
                        budget=budget,
                        requests=None if app is None else app.requests,
                    )
                    self._write_stop_event(outcome.project_result)
                    if installed_project_runtime and project_runtime is not None:
                        clear_project_runtime(project_runtime)
                        installed_project_runtime = False
                    detach(handle)
            outcome = self._with_runtime_stop_result(outcome, handle.stop_result)
            if server_errors:
                from dataclasses import replace
                outcome = replace(
                    outcome, exit_code=3, cleanup_errors=outcome.cleanup_errors + tuple(server_errors),
                )
            record_stop(outcome)
            return outcome.exit_code or (1 if runtime_failure is not None else 0)
        except BaseException as error:
            self._startup_failure_code = self._error_code(error)
            failure = context.startup_failure
            if outcome is not None and handle is not None:
                outcome = self._with_runtime_stop_result(outcome, handle.stop_result)
                record_stop(outcome)
            record_startup_failure(
                self._error_code(error),
                failure.rollback_result if failure is not None else getattr(handle, 'stop_result', None),
            )
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
            stop_event.set()

    def _wait_for_stop(self, stop_event, stop_file, deadline, handle):
        while not stop_event.is_set():
            if handle.ended.is_set():
                from ai_host.state import mark_failed
                code = handle.end_code or 'runtime_not_running'
                mark_failed(code)
                self._runtime_failure_message = f'serve runtime failed ({code}).'
                self.stdout.write(self._runtime_failure_message)
                stop_event.set()
                return code
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
            from dataclasses import replace
            return replace(outcome, runtime_result=stop_result)
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
                from ai_host.serve_control import bounded_output_exit
                bounded_output_exit(130, lambda: self._write_exit_line('serve forced exit.'))
            stop_event.set()

        for signum in self._signal_numbers():
            try:
                handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, handler)
            except (OSError, ValueError):
                continue
        return handlers

    def _begin_stop_budget(self):
        from ai_host.serve_control import StopBudget, start_watchdog

        if getattr(self, '_stop_budget', None) is None:
            self._stop_budget = StopBudget()
            start_watchdog(
                self._stop_budget,
                write_output=lambda: self._write_exit_line('serve cleanup failed.'),
            )
        return self._stop_budget

    def _write_exit_line(self, text):
        self.stdout.write(text)
        self.stdout.flush()
        self.stderr.flush()

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

    def _exit(self, code, *, message=None):
        if code == 130:
            from ai_host.serve_control import bounded_output_exit
            bounded_output_exit(130, lambda: self._write_exit_line(message or 'serve forced exit.'))
            return
        from ai_host.serve_exit import explicit_exit

        stop_event = getattr(self, '_stop_event', None)
        if stop_event is not None:
            stop_event.set()
        self._begin_stop_budget()
        explicit_exit(
            code, self.stdout, self.stderr,
            message=message or getattr(self, '_runtime_failure_message', None),
        )
