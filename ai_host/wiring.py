from copy import copy

from django.core.exceptions import DisallowedHost
from django.core.handlers.wsgi import WSGIRequest

from ai_host.host import log_auth_failed
from ai_host.settings import runtime_mount_path


def build_wsgi_application(django_app, runtime_app, *, is_accepting_requests=None):
    accepting = is_accepting_requests or (lambda: True)

    def application(environ, start_response):
        if not _host_is_allowed(environ):
            return _fixed_response(start_response, '400 Bad Request', b'Bad Request')
        if not accepting():
            return _fixed_response(
                start_response,
                '503 Service Unavailable',
                b'Service Unavailable',
                headers=(('Retry-After', '2'),),
            )
        mount_path = runtime_mount_path()
        path_info = environ.get('PATH_INFO') or ''
        if path_info == mount_path or path_info.startswith(mount_path + '/'):
            mounted = _mounted_environ(environ, mount_path)
            return runtime_app(mounted, _auth_logging_start_response(mounted, start_response))
        return django_app(environ, start_response)

    return application


def _host_is_allowed(environ):
    try:
        WSGIRequest(environ).get_host()
        return True
    except DisallowedHost:
        return False


def _mounted_environ(environ, mount_path):
    mounted = copy(environ)
    script_name = mounted.get('SCRIPT_NAME', '')
    mounted['SCRIPT_NAME'] = script_name.rstrip('/') + mount_path
    path_info = mounted.get('PATH_INFO') or ''
    mounted['PATH_INFO'] = path_info[len(mount_path):] or ''
    return mounted


def _fixed_response(start_response, status, body, *, headers=()):
    response_headers = [('Content-Type', 'text/plain'), ('Content-Length', str(len(body)))]
    response_headers.extend(headers)
    start_response(status, response_headers)
    return [body]


def _auth_logging_start_response(environ, start_response):
    logged = False

    def wrapper(status, headers, exc_info=None):
        nonlocal logged
        if not logged and str(status).startswith('401 '):
            logged = True
            log_auth_failed(
                f"{environ.get('SCRIPT_NAME', '')}{environ.get('PATH_INFO', '')}",
                environ.get('REMOTE_ADDR'),
                'authentication_required',
            )
        if exc_info is None:
            return start_response(status, headers)
        return start_response(status, headers, exc_info)

    return wrapper
