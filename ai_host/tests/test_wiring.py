from io import BytesIO

from django.test import SimpleTestCase, override_settings

from ai_host.wiring import build_wsgi_application


def call_wsgi(app, path, *, host='127.0.0.1:8023', query=''):
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured['status'] = status
        captured['headers'] = dict(headers)

    environ = {
        'REQUEST_METHOD': 'GET',
        'PATH_INFO': path,
        'SCRIPT_NAME': '',
        'QUERY_STRING': query,
        'SERVER_NAME': '127.0.0.1',
        'SERVER_PORT': '8023',
        'HTTP_HOST': host,
        'REMOTE_ADDR': '127.0.0.1',
        'wsgi.url_scheme': 'http',
        'wsgi.input': BytesIO(b''),
    }
    body = b''.join(app(environ, start_response))
    return captured['status'], captured['headers'], body


class RecordingApp:
    def __init__(self, label):
        self.label = label
        self.calls = []

    def __call__(self, environ, start_response):
        self.calls.append({
            'SCRIPT_NAME': environ.get('SCRIPT_NAME', ''),
            'PATH_INFO': environ.get('PATH_INFO', ''),
            'QUERY_STRING': environ.get('QUERY_STRING', ''),
        })
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [self.label.encode('ascii')]


class TestWsgiWiring(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=['127.0.0.1', 'localhost', '[::1]'], METRICS_BASE_URL='')
    def test_shouldRejectInvalidHostBeforeDjangoOrRuntime(self):
        django_app = RecordingApp('django')
        runtime_app = RecordingApp('runtime')
        app = build_wsgi_application(django_app, runtime_app)

        status, headers, body = call_wsgi(app, '/projects/', host='rebind.attacker.example')

        assert status == '400 Bad Request'
        assert body == b'Bad Request'
        assert django_app.calls == []
        assert runtime_app.calls == []

    @override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='/metrics/')
    def test_shouldMountRuntimeWithScriptNameAndPathInfo(self):
        django_app = RecordingApp('django')
        runtime_app = RecordingApp('runtime')
        app = build_wsgi_application(django_app, runtime_app)

        status, headers, body = call_wsgi(app, '/metrics/ai/assets/embed-host.js', query='v=1')

        assert status == '200 OK'
        assert body == b'runtime'
        assert runtime_app.calls == [{
            'SCRIPT_NAME': '/metrics/ai',
            'PATH_INFO': '/assets/embed-host.js',
            'QUERY_STRING': 'v=1',
        }]
        assert django_app.calls == []

    @override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='')
    def test_shouldSendOtherPathsToDjango(self):
        django_app = RecordingApp('django')
        runtime_app = RecordingApp('runtime')
        app = build_wsgi_application(django_app, runtime_app)

        status, headers, body = call_wsgi(app, '/projects/')

        assert status == '200 OK'
        assert body == b'django'
        assert django_app.calls == [{'SCRIPT_NAME': '', 'PATH_INFO': '/projects/', 'QUERY_STRING': ''}]
        assert runtime_app.calls == []

    @override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='')
    def test_shouldReturnRetryAfterWhenStoppingBeforeAuthentication(self):
        django_app = RecordingApp('django')
        runtime_app = RecordingApp('runtime')
        app = build_wsgi_application(django_app, runtime_app, is_accepting_requests=lambda: False)

        status, headers, body = call_wsgi(app, '/ai/')

        assert status == '503 Service Unavailable'
        assert headers['Retry-After'] == '2'
        assert body == b'Service Unavailable'
        assert django_app.calls == []
        assert runtime_app.calls == []
