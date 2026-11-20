import asyncio
from collections import Counter
from dataclasses import replace
from html.parser import HTMLParser
import json
import threading
import time

from ai_base_runtime.apps import AgentDefinition, AppPackage, AppRoute


class RuntimeProbe:
    """Controlled App handlers; all transport and lifetime behavior is real."""

    def __init__(self, *, spacing_events=8):
        self.stream_release = threading.Event()
        self.short_release = threading.Event()
        self.loop_entered = threading.Event()
        self.loop_release = threading.Event()
        self.spacing_events = spacing_events
        self._counts = Counter()
        self._lock = threading.Lock()
        self.handle = None
        self.server = None
        self.app_id = 'qualification'

    def count(self, name):
        with self._lock:
            return self._counts[name]

    def increment(self, name, value=1):
        with self._lock:
            self._counts[name] += value

    def release(self):
        self.stream_release.set()
        self.short_release.set()
        self.loop_release.set()

    async def echo(self, request):
        self.increment('echo')
        return {'principal': request.principal.id, 'bytes': len(request.body)}

    async def slow(self, request):
        self.increment('short')
        try:
            while not self.short_release.is_set():
                await asyncio.sleep(0.005)
            return {'done': True}
        finally:
            self.increment('short_done')

    async def fail(self, request):
        self.increment('fail')
        raise ValueError('synthetic-private-host-probe-error')

    async def lag(self, request):
        self.loop_entered.set()
        self.loop_release.wait(4)
        return {'released': self.loop_release.is_set()}

    async def misuse(self, request):
        from ai_base_runtime import RuntimeUsageError

        try:
            self.handle.blocking.chat.list_sessions(
                request.principal, app_id=self.app_id, limit=1, timeout=1,
            )
        except RuntimeUsageError as error:
            return {'code': error.code}
        return {'unexpected': 'loop-thread blocking call succeeded'}

    async def active(self, request):
        async for block in self._stream('active'):
            yield block

    async def idle(self, request):
        async for block in self._stream('idle'):
            yield block

    async def backlog(self, request):
        self.increment('streams')
        try:
            for index in range(512):
                yield {'type': 'backlog', 'index': index, 'data': 'x' * 16300}
                self.increment('backlog_blocks')
            while not self.stream_release.is_set():
                await asyncio.sleep(0.1)
        finally:
            self.increment('streams', -1)
            self.increment('streams_done')

    async def snapshot(self, request):
        with self._lock:
            counts = dict(self._counts)
        tasks = Counter(
            getattr(task.get_coro(), '__qualname__', type(task.get_coro()).__qualname__)
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        )
        config = request._runtime.host.config
        return {
            'counts': counts, 'tasks': dict(tasks),
            'threads': sorted(thread.name for thread in threading.enumerate() if thread.is_alive()),
            'pending_bytes': sum(channel.total_outbufs_len for channel in
                                 tuple(self.server.active_channels.values())) if self.server else 0,
            'limits': {
                'heartbeat': config.lifecycle.heartbeat_interval_seconds,
                'streams': config.http_limits.max_streams, 'requests': config.http_limits.max_requests,
                'terminal_grace': config.lifecycle.http_close_timeout_seconds,
            },
        }

    async def spacing(self, request):
        for index in range(self.spacing_events):
            yield json.dumps({'type': 'chunk', 'index': index}).encode() + b'\n'
            await asyncio.sleep(0.1)

    async def _stream(self, kind):
        self.increment('streams')
        try:
            index = 0
            while not self.stream_release.is_set():
                if kind == 'active':
                    yield json.dumps({'type': 'chunk', 'index': index}).encode() + b'\n'
                    index += 1
                await asyncio.sleep(0.1)
        finally:
            self.increment('streams', -1)
            self.increment('streams_done')

    def package(self, base=None):
        self.app_id = base.app_id if base is not None else 'qualification'
        routes = tuple(AppRoute(
            operation_id=f'qualification.{name}', method='GET',
            path=f'/api/qualification/{name}', handler=getattr(self, name),
            stream=name in {'active', 'idle', 'spacing', 'backlog'},
        ) for name in ('echo', 'slow', 'fail', 'lag', 'misuse', 'active', 'idle', 'spacing', 'backlog', 'snapshot'))
        routes += (AppRoute(
            operation_id='qualification.body', method='POST',
            path='/api/qualification/body', handler=self.echo, max_request_body_bytes=8_388_608,
        ),)
        if base is not None:
            return replace(base, routes=(*base.routes, *routes))
        return AppPackage(
            app_id='qualification', agents=(AgentDefinition(name='agent', instructions='Synthetic validation.'),),
            routes=routes,
        )


class Events:
    def __init__(self, stream):
        self.stream, self.buffer = stream, b''

    def next(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'No complete event before deadline'
            block = self.stream.next_chunk(remaining)
            if not block:
                assert not self.buffer, 'Truncated event before EOF'
                return None
            self.buffer += block
        line, _, self.buffer = self.buffer.partition(b'\n')
        return json.loads(line)


class AssetParser(HTMLParser):
    def __init__(self, prefix):
        super().__init__()
        self.prefix, self.assets = prefix, []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        value = attributes.get('href') if tag == 'link' else attributes.get('src') if tag in {'script', 'img'} else None
        value = value.split('#')[0] if value else value
        if value and value.startswith(self.prefix) and value not in self.assets:
            self.assets.append(value)


def until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, 'Observable resource did not settle'
        time.sleep(0.01)
