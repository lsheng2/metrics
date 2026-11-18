from copy import copy
import threading
import time

from django.core.exceptions import DisallowedHost
from django.core.handlers.wsgi import WSGIRequest

from ai_host.host import log_auth_failed
from ai_host.settings import runtime_mount_path


class RequestTracker:
    def __init__(self):
        self._condition = threading.Condition()
        self._count = 0
        self._accepting = True

    @property
    def count(self):
        with self._condition:
            return self._count

    def admit(self, accepting):
        with self._condition:
            if not self._accepting or not accepting():
                return False
            self._count += 1
            return True

    def release(self):
        with self._condition:
            self._count -= 1
            self._condition.notify_all()

    def stop_accepting(self):
        with self._condition:
            self._accepting = False

    def wait_empty(self, deadline):
        with self._condition:
            while self._count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(min(0.5, remaining))
            return True


class TrackedResponse:
    def __init__(self, response, requests):
        self._response = response
        self._requests = requests
        self._closed = False
        self._lock = threading.Lock()

    def __iter__(self):
        return iter(self._response)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            close = getattr(self._response, 'close', None)
            if close is not None:
                close()
        finally:
            self._requests.release()


def build_wsgi_application(django_app, runtime_app, *, is_accepting_requests=None):
    accepting = is_accepting_requests or (lambda: True)
    requests = RequestTracker()

    def application(environ, start_response):
        if not _host_is_allowed(environ):
            return _fixed_response(start_response, '400 Bad Request', b'Bad Request')
        if not requests.admit(accepting):
            return _fixed_response(
                start_response,
                '503 Service Unavailable',
                b'Service Unavailable',
                headers=(('Retry-After', '2'),),
            )
        try:
            mount_path = runtime_mount_path()
            path_info = environ.get('PATH_INFO') or ''
            if path_info == mount_path or path_info.startswith(mount_path + '/'):
                mounted = _mounted_environ(environ, mount_path)
                response = runtime_app(mounted, _auth_logging_start_response(mounted, start_response))
            else:
                response = django_app(environ, start_response)
            return TrackedResponse(response, requests)
        except BaseException:
            requests.release()
            raise

    application.requests = requests
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
