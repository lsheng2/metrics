from io import BytesIO

import pytest
from django.test import override_settings

from ai_host.wiring import build_wsgi_application


def environ(path='/projects/'):
    return {
        'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'SCRIPT_NAME': '',
        'SERVER_NAME': '127.0.0.1', 'SERVER_PORT': '80',
        'HTTP_HOST': '127.0.0.1', 'wsgi.url_scheme': 'http',
        'wsgi.input': BytesIO(),
    }


@pytest.mark.parametrize('path', ['/projects/', '/ai/stream'])
@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='')
def test_stream_is_inflight_until_close_even_after_application_return_and_exhaustion(path):
    closed = []

    class Response:
        def __iter__(self):
            yield b'first'
            yield b'last'

        def close(self):
            closed.append(True)

    def handler(env, start_response):
        start_response('200 OK', [])
        return Response()

    app = build_wsgi_application(handler, handler)
    result = app(environ(path), lambda *args: None)
    assert app.requests.count == 1
    assert list(result) == [b'first', b'last']
    assert app.requests.count == 1
    result.close()
    assert app.requests.count == 0
    result.close()
    assert closed == [True]


@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='')
@pytest.mark.parametrize('failure', ['application', 'iteration', 'close'])
def test_exception_and_abort_return_the_inflight_slot(failure):
    class Response:
        def __iter__(self):
            if failure == 'iteration':
                raise ValueError('synthetic iteration failure')
            yield b'first'

        def close(self):
            if failure == 'close':
                raise ValueError('synthetic close failure')

    def handler(env, start_response):
        if failure == 'application':
            raise ValueError('synthetic application failure')
        return Response()

    app = build_wsgi_application(handler, handler)
    if failure == 'application':
        with pytest.raises(ValueError):
            app(environ(), lambda *args: None)
    else:
        response = app(environ(), lambda *args: None)
        if failure == 'iteration':
            with pytest.raises(ValueError):
                list(response)
        try:
            response.close()
        except ValueError:
            assert failure == 'close'
    assert app.requests.count == 0


@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='')
def test_stop_prevents_new_admission_and_preserves_host_rejection_order():
    def handler(*args):
        pytest.fail('stopped host must not enter either downstream application')

    app = build_wsgi_application(handler, handler)
    app.requests.stop_accepting()
    statuses = []
    response = app(environ(), lambda status, headers: statuses.append((status, headers)))
    assert b''.join(response) == b'Service Unavailable'
    assert statuses[-1][0] == '503 Service Unavailable'
    assert ('Retry-After', '2') in statuses[-1][1]
    request = environ()
    request['HTTP_HOST'] = 'hostile.example'
    response = app(request, lambda status, headers: statuses.append((status, headers)))
    assert b''.join(response) == b'Bad Request'
    assert statuses[-1][0] == '400 Bad Request'
    assert app.requests.count == 0
