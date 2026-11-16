from http.client import HTTPConnection
import threading

from waitress import create_server

from ai_host.lifecycle import stop_owned_resources
from ai_host.tests.test_lifecycle import FakeHandle


def test_stop_closes_an_idle_keepalive_channel_and_joins_the_real_waitress_thread():
    def application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '2')])
        return [b'ok']

    server = create_server(application, host='127.0.0.1', port=0, threads=1, asyncore_loop_timeout=0.05)
    thread = threading.Thread(target=server.run, name='publication-stop-probe')
    connection = HTTPConnection('127.0.0.1', int(server.effective_port), timeout=5)
    thread.start()
    try:
        connection.request('GET', '/', headers={'Connection': 'keep-alive'})
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == b'ok'
        assert server.active_channels
        result = stop_owned_resources(
            handle=FakeHandle(), server=server, server_thread=thread, project_runtime=None,
        )
        assert result.exit_code == 0, result
        assert not thread.is_alive()
        assert not server.active_channels
    finally:
        connection.close()
        for channel in tuple(server.active_channels.values()):
            channel.handle_close()
        server.close()
        server.task_dispatcher.shutdown(cancel_pending=True, timeout=0.5)
        thread.join(2)
        assert not thread.is_alive()
