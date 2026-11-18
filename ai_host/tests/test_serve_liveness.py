import io
import threading
import time
from types import SimpleNamespace

from ai_host.management.commands.serve import Command
from ai_host.state import attach, detach, get_running_handle
from ai_host.tests.test_lifecycle import FakeHandle


def test_unexpected_runtime_end_stops_the_host_instead_of_only_hiding_its_handle():
    handle = FakeHandle()
    handle.ended = threading.Event()
    handle.ended.set()
    handle.end_code = 'loop_failed'
    stop = threading.Event()
    output = io.StringIO()
    command = Command(stdout=output)
    attach(handle)
    try:
        assert get_running_handle() is None
        started = time.monotonic()
        result = command._wait_for_stop(stop, None, started + 0.8, handle)
        assert result == 'loop_failed'
        assert stop.is_set()
        assert time.monotonic() - started < 0.5
        assert output.getvalue() == 'serve runtime failed (loop_failed).\n'
    finally:
        detach(handle)


def test_ordinary_stop_is_not_relabelled_runtime_failure():
    stop = threading.Event()
    stop.set()
    handle = SimpleNamespace(ended=threading.Event(), end_code=None)
    output = io.StringIO()
    result = Command(stdout=output)._wait_for_stop(stop, None, None, handle)
    assert result is None
    assert output.getvalue() == ''


def test_failed_runtime_phase_and_code_survive_handle_detachment():
    from ai_host.state import get_lifecycle

    handle = FakeHandle()
    handle.ended = threading.Event()
    handle.end_code = 'loop_failed'
    attach(handle)
    try:
        assert get_lifecycle().phase == 'running'
        handle.ended.set()
        assert get_running_handle() is None
        assert get_lifecycle().phase == 'failed'
        assert get_lifecycle().error_codes == ('loop_failed',)
    finally:
        detach(handle)
    assert get_lifecycle().phase == 'failed'
    assert get_lifecycle().handle is None
