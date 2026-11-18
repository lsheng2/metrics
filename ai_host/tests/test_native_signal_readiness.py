from types import SimpleNamespace
from urllib.error import URLError

import pytest

from ai_host.tests import test_serve_native_signal as signals


@pytest.mark.parametrize('content,expected', [
    (None, False), ('', False), ('flu', False), ('drain', False), ('flush', True),
])
def test_phase_observation_requires_the_complete_expected_value(tmp_path, content, expected):
    marker = tmp_path / 'phase'
    if content is not None:
        marker.write_text(content, encoding='utf-8')
    assert signals.phase_reached(marker, 'flush') is expected


def unavailable_http(*args, **kwargs):
    raise URLError('listener is already closed')


@pytest.mark.parametrize('phase', ['drain', 'flush'])
def test_lifetime_cleanup_can_precede_the_first_http_observation(tmp_path, monkeypatch, phase):
    marker, log = tmp_path / 'phase', tmp_path / 'serve.log'
    marker.write_text(phase, encoding='utf-8')
    log.write_text('cleanup deadline reached', encoding='utf-8')
    statuses = iter([None, 3])
    process = SimpleNamespace(poll=lambda: next(statuses))
    opener = SimpleNamespace(open=unavailable_http)
    monkeypatch.setattr(signals.time, 'sleep', lambda seconds: None)
    assert signals.wait_until_ready(process, opener, 1, log, marker, 'lifetime', phase) is None


@pytest.mark.parametrize('trigger,phase', [
    ('stop-file', 'flush'), ('SIGTERM', 'flush'), ('lifetime', 'normal'),
])
def test_unrelated_phase_cannot_replace_http_readiness(tmp_path, monkeypatch, trigger, phase):
    marker, log = tmp_path / 'phase', tmp_path / 'serve.log'
    marker.write_text(phase, encoding='utf-8')
    log.write_text('service did not become ready', encoding='utf-8')
    statuses = iter([None, 3])
    process = SimpleNamespace(poll=lambda: next(statuses))
    opener = SimpleNamespace(open=unavailable_http)
    monkeypatch.setattr(signals.time, 'sleep', lambda seconds: None)
    with pytest.raises(AssertionError, match='did not become ready'):
        signals.wait_until_ready(process, opener, 1, log, marker, trigger, phase)


def test_cleanup_marker_cannot_hide_an_exited_process(tmp_path):
    marker, log = tmp_path / 'phase', tmp_path / 'serve.log'
    marker.write_text('flush', encoding='utf-8')
    log.write_text('process already exited', encoding='utf-8')
    with pytest.raises(AssertionError, match='already exited'):
        signals.wait_until_ready(
            SimpleNamespace(poll=lambda: 3), SimpleNamespace(open=unavailable_http),
            1, log, marker, 'lifetime', 'flush',
        )
