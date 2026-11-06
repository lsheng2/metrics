from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from itertools import islice


def _read(function, value, check):
    check()
    result = function(value)
    check()
    return result


@contextmanager
def ordered_read_map(function, items, check):
    items = tuple(items)
    check()
    if len(items) < 2:
        yield (_read(function, item, check) for item in items)
        return
    iterator = iter(items)
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='archive-read')
    pending = deque()

    def results():
        for item in islice(iterator, 4):
            check()
            pending.append(pool.submit(_read, function, item, check))
        while pending:
            check()
            value = pending.popleft().result()
            yield value
            for item in islice(iterator, 1):
                check()
                pending.append(pool.submit(_read, function, item, check))

    try:
        yield results()
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
