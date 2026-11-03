from pathlib import Path
import json
import socketserver
import time

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.management.base import BaseCommand, CommandError
from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer, get_internal_wsgi_application

from project_management.app.api.project_runs import (
    RuntimeStopResult,
    build_project_runtime,
    clear_project_runtime,
    install_project_runtime,
)


class Command(BaseCommand):
    help = 'Serve the project dashboard with an explicitly started project run runtime.'

    def add_arguments(self, parser):
        parser.add_argument('--host', default='127.0.0.1')
        parser.add_argument('--port', type=int, required=True)
        parser.add_argument('--stop-file')
        parser.add_argument('--lifetime-seconds', type=int)

    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        if host not in {'127.0.0.1', 'localhost', '::1'} or not 1 <= port <= 65535:
            raise CommandError('project_serve only accepts loopback host and a valid port.')
        stop_file = self._stop_file(options.get('stop_file'))
        lifetime_seconds = self._lifetime(options.get('lifetime_seconds'))
        runtime = None
        installed = False
        primary_error = None
        primary_phase = 'serve'
        cleanup_error = None
        try:
            runtime = build_project_runtime()
            runtime = install_project_runtime(runtime)
            installed = True
            try:
                try:
                    runtime.start()
                except Exception as error:
                    primary_phase = 'startup'
                    primary_error = error
                else:
                    application = StaticFilesHandler(get_internal_wsgi_application())
                    self._serve(host, port, application, stop_file, lifetime_seconds)
            except Exception as error:
                primary_error = error
            finally:
                cleanup_error = self._cleanup_runtime(runtime, installed)
        except Exception as error:
            if installed:
                cleanup_error = cleanup_error or self._cleanup_runtime(runtime, installed)
            raise CommandError(self._safe_error('startup', error)) from None
        if primary_error is not None:
            raise CommandError(self._safe_error(primary_phase, primary_error)) from None
        if cleanup_error is not None:
            raise CommandError(self._safe_error('cleanup', cleanup_error)) from None

    def _cleanup_runtime(self, runtime, installed):
        stop_error = None
        result = None
        if runtime is not None and installed:
            try:
                result = runtime.stop(620)
            except Exception as error:
                stop_error = error
                result = RuntimeStopResult(False, None, ())
            finally:
                self._write_stop_event(result)
                try:
                    clear_project_runtime(runtime)
                except Exception as error:
                    stop_error = stop_error or error
        if stop_error is not None:
            return stop_error
        if result is not None and (not result.stopped or result.unresolved):
            return RuntimeError('project runtime did not stop cleanly')
        return None

    def _write_stop_event(self, result):
        self.stdout.write(json.dumps({
            'schema_version': 1,
            'event': 'project_runtime_stopped',
            'stopped': result.stopped,
            'active_operation_id': result.active_operation_id,
            'unresolved': list(result.unresolved),
        }, separators=(',', ':')))

    def _safe_error(self, phase, error):
        code = getattr(error, 'code', None)
        suffix = f' ({code})' if isinstance(code, str) and code else ''
        return f'project_serve {phase} failed{suffix}.'

    def _serve(self, host, port, application, stop_file, lifetime_seconds):
        server_class = type('ProjectRunWSGIServer', (socketserver.ThreadingMixIn, WSGIServer), {})
        server = server_class((host, port), WSGIRequestHandler, ipv6=host == '::1')
        server.daemon_threads = True
        server.timeout = 0.5
        server.set_app(application)
        deadline = None if lifetime_seconds is None else time.monotonic() + lifetime_seconds
        try:
            while True:
                if stop_file is not None and stop_file.exists():
                    return
                if deadline is not None and time.monotonic() >= deadline:
                    return
                server.handle_request()
        finally:
            server.server_close()

    def _stop_file(self, value):
        if value in {None, ''}:
            return None
        path = Path(value)
        if not path.is_absolute():
            raise CommandError('--stop-file must be an absolute path.')
        return path

    def _lifetime(self, value):
        if value is None:
            return None
        if type(value) is not int or value <= 0:
            raise CommandError('--lifetime-seconds must be positive.')
        return value
