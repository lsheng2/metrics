from io import BytesIO

import pytest
from django.test import SimpleTestCase, override_settings

from ai_host.models import RuntimeAuditEvent
from ai_host.wiring import build_wsgi_application


def call_wsgi(app, path, *, host='127.0.0.1:8023', query='', remote_addr='127.0.0.1'):
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured['status'] = status
        captured['headers'] = dict(headers)
        captured.setdefault('writes', [])

        def write(data):
            captured['writes'].append(data)

        return write

    environ = {
        'REQUEST_METHOD': 'GET',
        'PATH_INFO': path,
        'SCRIPT_NAME': '',
        'QUERY_STRING': query,
        'SERVER_NAME': '127.0.0.1',
        'SERVER_PORT': '8023',
        'HTTP_HOST': host,
        'REMOTE_ADDR': remote_addr,
        'wsgi.url_scheme': 'http',
        'wsgi.input': BytesIO(b''),
    }
    response = app(environ, start_response)
    body = b''.join(captured.get('writes', ())) + b''.join(response)
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


class RuntimeUnauthorizedApp:
    def __call__(self, environ, start_response):
        write = start_response('401 Unauthorized', [('Content-Type', 'text/plain')])
        write(b'auth ')
        return [b'required']


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


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['127.0.0.1'], METRICS_BASE_URL='/metrics/')
def test_runtime_mount_401_logs_sanitized_auth_failure_without_audit_write(caplog):
    django_app = RecordingApp('django')
    app = build_wsgi_application(django_app, RuntimeUnauthorizedApp())

    before = RuntimeAuditEvent.objects.count()
    status, headers, body = call_wsgi(
        app,
        '/metrics/ai/apps/probe/api/identity',
        query='token=must-not-log',
        remote_addr='127.0.0.44',
    )

    assert status == '401 Unauthorized'
    assert body == b'auth required'
    assert RuntimeAuditEvent.objects.count() == before
    assert django_app.calls == []
    records = [record for record in caplog.records if record.getMessage() == 'ai_auth_failed']
    assert len(records) == 1
    assert (records[0].path, records[0].client_addr, records[0].reason) == (
        '/metrics/ai/apps/probe/api/identity',
        '127.0.0.44',
        'authentication_required',
    )
    assert 'token=must-not-log' not in repr(records)
