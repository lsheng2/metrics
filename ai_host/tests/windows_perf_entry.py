"""Isolated baseline/current-host fixture; not a product command or compatibility mode."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import signal
import socket
import socketserver
import sys
import threading


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def safe_root(value):
    from scripts.validation.project_full_stack_support import reject_reparse_components

    path = Path(value)
    reject_reparse_components(path)
    resolved = path.resolve(strict=True)
    if (not path.is_absolute() or resolved != path.absolute()
            or resolved.is_relative_to(ROOT) or ROOT.is_relative_to(resolved)):
        raise ValueError('Expected an external, canonical owned root')
    owner = json.loads((resolved / 'owner.json').read_text(encoding='utf-8'))
    if owner != {'owner': 'windows-host-qualification', 'root': str(resolved)}:
        raise ValueError('Wrong qualification owner')
    return resolved


def network_guard(stack):
    from unittest.mock import patch
    from scripts.validation.run_report_authoring_tests import (
        guarded_connect, guarded_create_connection, guarded_getaddrinfo,
    )
    resolve = socket.getaddrinfo
    guarded_resolve = guarded_getaddrinfo(resolve)

    def getaddrinfo(host, *args, **kwargs):
        if host in {'0.0.0.0', '::'}:
            return resolve(host, *args, **kwargs)
        return guarded_resolve(host, *args, **kwargs)

    stack.enter_context(patch.object(socket.socket, 'connect', guarded_connect(socket.socket.connect)))
    stack.enter_context(patch.object(socket.socket, 'connect_ex', guarded_connect(socket.socket.connect_ex)))
    stack.enter_context(patch.object(socket, 'create_connection', guarded_create_connection(socket.create_connection)))
    stack.enter_context(patch.object(socket, 'getaddrinfo', getaddrinfo))


def baseline(port, stop_file):
    from django.core.handlers.wsgi import WSGIHandler
    from django.core.servers.basehttp import WSGIRequestHandler, WSGIServer
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from project_management.runtime import clear_project_runtime, install_project_runtime
    from ai_host.tests.windows_perf_fixture import build_idle_runtime, WORKER

    stopped = threading.Event()
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK):
        signal.signal(number, lambda *args: stopped.set())
    server_class = type('BaselineWSGIServer', (socketserver.ThreadingMixIn, WSGIServer), {})
    server = server_class(('127.0.0.1', port), WSGIRequestHandler)
    server.daemon_threads, server.timeout = True, 0.5
    server.set_app(StaticFilesHandler(WSGIHandler()))
    runtime = install_project_runtime(build_idle_runtime())
    runtime.start()
    try:
        while not stopped.is_set() and not stop_file.exists():
            server.handle_request()
    finally:
        server.server_close()
        runtime.request_stop()
        result = runtime.wait_stopped(620)
        clear_project_runtime(runtime)
        print(json.dumps({'event': 'baseline_stopped', 'stopped': result.stopped,
                          'unresolved': result.unresolved, 'worker': WORKER}), flush=True)
    return 0 if result.stopped and not result.unresolved and not WORKER['executed'] else 3


def access_log(application):
    import logging
    logger = logging.getLogger('django.server')

    def wrapped(environ, start_response):
        line = f"{environ.get('REQUEST_METHOD')} {environ.get('SCRIPT_NAME', '')}{environ.get('PATH_INFO')} {environ.get('SERVER_PROTOCOL')}"

        def respond(status, headers, exc_info=None):
            code = int(status[:3])
            length = next((value for key, value in headers if key.lower() == 'content-length'), '-')
            log = logger.error if code >= 500 else logger.warning if code >= 400 else logger.info
            log('"%s" %s %s', line, code, length, extra={'status_code': code})
            return start_response(status, headers, exc_info)

        return application(environ, respond)

    wrapped.requests = application.requests
    return wrapped


def main():
    from ai_host.exit_inventory import install_exit_capture
    install_exit_capture()
    from unittest.mock import patch
    from scripts.validation.project_full_stack_support import reject_reparse_components
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('seed', 'serve'))
    parser.add_argument('--root', required=True)
    parser.add_argument('--instance')
    parser.add_argument('--role', choices=('baseline', 'candidate'))
    parser.add_argument('--port', type=int)
    parser.add_argument('--production', action='store_true')
    parser.add_argument('--spacing-events', type=int, default=8)
    args = parser.parse_args()
    root = safe_root(args.root)
    instance = root if args.action == 'seed' else Path(args.instance)
    reject_reparse_components(instance)
    if not instance.is_absolute():
        raise ValueError('Expected absolute instance path')
    instance = instance.resolve(strict=True)
    if instance != root and not instance.is_relative_to(root):
        raise ValueError('Unowned instance')
    if args.action == 'seed' and (root / 'catalog.sqlite3').exists():
        raise ValueError('Refusing to replace a seeded database')
    from ai_host.tests import windows_perf_fixture as fixture
    with ExitStack() as stack:
        network_guard(stack)
        fixture.configure(root, instance, debug=not args.production)
        import django
        django.setup()
        from django.core.management import call_command
        if args.action == 'seed':
            call_command('migrate', interactive=False, verbosity=0)
            (root / 'seed.json').write_text(json.dumps(fixture.seed_projects()), encoding='utf-8')
            return 0
        fixture.bootstrap(json.loads((root / 'seed.json').read_text(encoding='utf-8')), instance)
        if args.production:
            call_command('collectstatic', interactive=False, verbosity=0)
        stop_file = instance / 'stop'
        if args.role == 'baseline':
            return baseline(args.port, stop_file)
        from ai_host.tests.conformance_runtime_probe import RuntimeProbe
        from ai_host import package, wiring
        from project_management import runtime
        probe = RuntimeProbe(spacing_events=args.spacing_events)
        stack.enter_context(patch.object(package, 'METRICS_APP', probe.package(package.METRICS_APP)))
        stack.enter_context(patch.object(runtime, 'build_project_runtime', fixture.build_idle_runtime))
        build = wiring.build_wsgi_application
        stack.enter_context(patch.object(
            wiring, 'build_wsgi_application', lambda *a, **kw: access_log(build(*a, **kw)),
        ))
        call_command('serve', host='127.0.0.1', port=args.port, stop_file=str(stop_file), lifetime_seconds=1200)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
