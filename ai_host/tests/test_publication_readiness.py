from http.client import BadStatusLine, IncompleteRead, RemoteDisconnected
from types import SimpleNamespace

import pytest

from ai_host.tests import publication_process_fixture as fixture


@pytest.mark.parametrize('transient', [
    BadStatusLine('GET /api/health HTTP/1.1\r\n'),
    RemoteDisconnected('startup connection closed'),
    IncompleteRead(b'partial', 10),
])
def test_startup_readiness_waits_for_a_valid_http_response(tmp_path, monkeypatch, transient):
    replies = iter([transient, {'database': 'ok'}])

    def request(*args, **kwargs):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(fixture, 'request_json', request)
    monkeypatch.setattr(fixture.time, 'sleep', lambda seconds: None)
    assert fixture.await_ready(
        SimpleNamespace(poll=lambda: None), 'http://127.0.0.1:1/api/health',
        {}, tmp_path / 'unused.log', timeout=1,
    ) == {'database': 'ok'}


def test_invalid_http_cannot_extend_the_readiness_deadline(tmp_path, monkeypatch):
    clock = iter([0.0, 1.1])
    log = tmp_path / 'startup.log'
    log.write_text('startup did not finish', encoding='utf-8')

    def invalid(*args, **kwargs):
        raise BadStatusLine('GET /api/health HTTP/1.1\r\n')

    monkeypatch.setattr(fixture, 'request_json', invalid)
    monkeypatch.setattr(fixture.time, 'monotonic', lambda: next(clock))
    with pytest.raises(AssertionError):
        fixture.await_ready(
            SimpleNamespace(poll=lambda: None), 'http://127.0.0.1:1/api/health',
            {}, log, timeout=1,
        )


def test_readiness_still_refuses_an_exited_owned_process(tmp_path, monkeypatch):
    log = tmp_path / 'serve.log'
    log.write_text('owned process ended', encoding='utf-8')

    def unexpected(*args, **kwargs):
        raise AssertionError('HTTP must not hide a dead process')

    monkeypatch.setattr(fixture, 'request_json', unexpected)
    with pytest.raises(AssertionError, match='owned process ended'):
        fixture.await_ready(SimpleNamespace(poll=lambda: 3), 'http://127.0.0.1:1/', {}, log)
