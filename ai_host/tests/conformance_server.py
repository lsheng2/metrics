from contextlib import contextmanager
from http.client import HTTPConnection
import threading
from django.core.handlers.wsgi import WSGIHandler
from waitress import create_server

from ai_base_runtime import request_body_policy
from ai_base_runtime.testkit import HttpObservation
from ai_host.lifecycle import run_http_server, stop_owned_resources
from ai_host.serve_control import StopBudget
from ai_host.settings import SERVER_THREADS
from ai_host.wiring import build_wsgi_application


class MetricsConformanceServer:
    def __init__(self, server, root_path):
        self.base_url = f'http://127.0.0.1:{server.effective_port}'
        self.root_path = root_path
        self._port = int(server.effective_port)

    def _connect(self, method, path, headers, body, timeout, *, close_connection=True):
        connection = HTTPConnection('127.0.0.1', self._port, timeout=timeout)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            names = {key.lower() for key, _ in headers}
            for key, value in headers:
                connection.putheader(key, value)
            if 'content-length' not in names and (body or method == 'POST'):
                connection.putheader('Content-Length', str(len(body)))
            if close_connection and 'connection' not in names:
                connection.putheader('Connection', 'close')
            connection.endheaders(body)
            return connection, connection.getresponse()
        except BaseException:
            connection.close()
            raise

    def request(self, method, path, *, headers, body=b'', timeout, close_connection=True):
        connection, response = self._connect(
            method, path, headers, body, timeout, close_connection=close_connection,
        )
        try:
            return HttpObservation(response.status, tuple(response.getheaders()), response.read())
        finally:
            response.close()
            connection.close()

    def open_stream(self, path, *, headers, timeout):
        connection, response = self._connect('GET', path, headers, b'', timeout)
        if response.status != 200:
            response.close()
            connection.close()
            raise AssertionError(f'Stream returned HTTP {response.status}')
        return MetricsConformanceStream(connection, response)


class MetricsConformanceStream:
    def __init__(self, connection, response):
        self.connection, self.response = connection, response

    def next_chunk(self, timeout):
        # The response owns the socket once a Connection: close response starts.
        raw = self.response.fp
        if raw is None:
            return b''
        raw.raw._sock.settimeout(timeout)
        return self.response.read1(65536)

    def close(self):
        self.response.close()
        self.connection.close()


@contextmanager
def metrics_server(session, *, probe_disconnect=False, accepting_requests=None):
    application = build_wsgi_application(
        WSGIHandler(), session.handle.wsgi_app(), is_accepting_requests=accepting_requests,
    )
    cap = request_body_policy(session.settings, session.apps).max_request_body_bytes
    server = create_server(
        application, host='127.0.0.1', port=0, threads=SERVER_THREADS,
        channel_request_lookahead=1, max_request_body_size=cap + 1,
    )
    server_errors = []
    thread = threading.Thread(
        target=run_http_server, args=(server, server_errors), name='metrics-conformance-http', daemon=False,
    )
    thread.start()
    try:
        yield MetricsConformanceServer(server, session.host.config.root_path)
    finally:
        outcome = stop_owned_resources(
            handle=session.handle, server=server, server_thread=thread, project_runtime=None,
            budget=StopBudget(), requests=application.requests,
        )
        assert outcome.exit_code == 0, outcome
        assert not thread.is_alive()
        assert not server_errors
