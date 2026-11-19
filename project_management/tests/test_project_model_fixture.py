import json
from io import BytesIO

from scripts.validation.project_model_fixture import (
    BoundedThreadingHTTPServer, Handler, MAX_REQUEST_BYTES, extract_task_input,
)


class FakeHandler(Handler):
    def __init__(self, headers, body=b'{}'):
        self.headers = headers
        self.rfile = BytesIO(body)


def test_model_fixture_rejects_missing_invalid_or_oversized_content_length():
    for value in (None, 'abc', '-1'):
        handler = FakeHandler({} if value is None else {'Content-Length': value})
        try:
            handler._content_length()
        except ValueError as error:
            assert str(error) == 'invalid_content_length'
        else:
            raise AssertionError('invalid content length was accepted')

    handler = FakeHandler({'Content-Length': str(MAX_REQUEST_BYTES + 1)})
    try:
        handler._content_length()
    except ValueError as error:
        assert str(error) == 'request_too_large'
    else:
        raise AssertionError('oversized content length was accepted')


def test_model_fixture_reads_only_declared_bounded_request_bytes():
    body = b'{"messages": []}trailing'
    handler = FakeHandler({'Content-Length': '16'}, body)

    length = handler._content_length()
    payload = json.loads(handler.rfile.read(length).decode('utf-8'))

    assert payload == {'messages': []}
    assert handler.rfile.read() == b'trailing'


def test_model_fixture_server_threads_do_not_block_close():
    assert BoundedThreadingHTTPServer.daemon_threads is True
    assert BoundedThreadingHTTPServer.block_on_close is False


def test_model_fixture_extracts_embedded_task_json_from_openai_messages():
    payload = {
        'messages': [{
            'role': 'user',
            'content': 'Use this input:\n```json\n{"binding":{"stable_id":"101"},"target_capture_id":"c"}\n```',
        }],
    }

    assert extract_task_input(payload) == {'binding': {'stable_id': '101'}, 'target_capture_id': 'c'}
