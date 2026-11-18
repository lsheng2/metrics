from pathlib import Path
import runpy
import socket
import sys
import traceback


def main(*, configure=None, prepare=None, diagnose_errors=True):
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from ai_host.exit_inventory import install_exit_capture
    install_exit_capture()
    scope = runpy.run_path(str(root / 'scripts/validation/run_report_authoring_tests.py'))
    original_settings = scope['test_settings']
    regular_getaddrinfo = scope['guarded_getaddrinfo']

    def listener_resolution(original, **options):
        guarded = regular_getaddrinfo(original, **options)

        def resolve(host, port, family=0, type=0, proto=0, flags=0):
            # Waitress resolves a passive wildcard even when using a pre-bound socket.
            if host in {None, '0.0.0.0', '::'} and flags & socket.AI_PASSIVE:
                return original(host, port, family, type, proto, flags)
            return guarded(host, port, family, type, proto, flags)

        return resolve

    def isolated_settings(temp):
        values = original_settings(temp)
        Path(values['METRICS_PROJECT_ARCHIVE_ROOT']).mkdir(parents=True)
        values.update({
            'DATABASES': {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(temp / 'catalog.sqlite3')}},
            'METRICS_PROJECT_RUN_ENABLED': True,
            'METRICS_PROJECT_ARCHIVE_AUTHOR_NAME': 'Synthetic Host Test',
            'METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL': 'synthetic@example.test',
            'METRICS_BASIC_AUTH_USERS': None,
            'METRICS_AI_MODEL_BASE_URL': '',
            'METRICS_AI_MODEL_NAME': '',
            'METRICS_AI_MODEL_API_KEY': '',
        })
        if configure is not None:
            values.update(configure(temp))
        return values

    def serve(arguments):
        from django.core.management import execute_from_command_line
        from ai_host.management.commands.serve import Command

        original_run = Command._run_bound_server

        def diagnosed_run(command, *args, **kwargs):
            try:
                return original_run(command, *args, **kwargs)
            except Exception:
                traceback.print_exc()
                raise

        if diagnose_errors:
            Command._run_bound_server = diagnosed_run
        execute_from_command_line(['manage.py', 'migrate', '--noinput', '--verbosity', '0'])
        if prepare is not None:
            prepare()
        execute_from_command_line([
            'manage.py', 'serve', '--host', '127.0.0.1', '--port', sys.argv[2],
            '--stop-file', sys.argv[3],
        ])
        return 0

    scope['run_tests'].__globals__['ROOT'] = Path(sys.argv[1])
    scope['run_tests'].__globals__['test_settings'] = isolated_settings
    scope['run_tests'].__globals__['guarded_getaddrinfo'] = listener_resolution
    scope['pytest'].main = serve
    return scope['run_tests']([])


if __name__ == '__main__':
    raise SystemExit(main())
