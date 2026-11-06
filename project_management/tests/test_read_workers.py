from threading import Barrier, Lock, current_thread

import pytest


@pytest.mark.parametrize('fail', [False, True])
def test_local_read_pool_is_bounded_ordered_and_closed_on_error(fail):
    from project_management.storage.read_workers import ordered_read_map

    barrier = Barrier(4, timeout=2)
    lock = Lock()
    active, peak, seen = [0], [0], set()

    def read(value):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            seen.add(current_thread())
        try:
            barrier.wait()
            if fail and value == 2:
                raise ValueError('owned read failed')
            return value * 2
        finally:
            with lock:
                active[0] -= 1

    if fail:
        with pytest.raises(ValueError, match='owned read failed'):
            with ordered_read_map(read, tuple(range(4)), lambda: None) as values:
                tuple(values)
    else:
        with ordered_read_map(read, tuple(range(8)), lambda: None) as values:
            assert tuple(values) == tuple(range(0, 16, 2))
    assert peak[0] == 4
    assert active[0] == 0
    assert seen and all(not worker.is_alive() for worker in seen)


def test_stopped_read_pool_does_not_schedule_new_work():
    from project_management.storage.read_workers import ordered_read_map

    calls = []

    def stopped():
        raise TimeoutError('read expired')

    with pytest.raises(TimeoutError):
        with ordered_read_map(calls.append, tuple(range(10)), stopped) as values:
            tuple(values)
    assert calls == []
