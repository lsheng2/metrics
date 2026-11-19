"""Observed NDJSON delivery and independent stream/short-request saturation."""
import base64
from contextlib import contextmanager
from http.client import HTTPConnection
import json
import math
import socket
import threading
import time
from urllib.parse import urlsplit

from scripts.validation.windows_host_samples import AUTH, client, finite, percentile


PROBE_PATH = '/ai/apps/metrics/api/qualification'


class Stream:
    def __init__(self, base, path, *, auth=AUTH):
        address = urlsplit(base)
        if address.scheme != 'http' or address.hostname != '127.0.0.1':
            raise ValueError('Only loopback native streams are permitted')
        self.connection = HTTPConnection(address.hostname, address.port, timeout=3)
        self.closed = threading.Event()
        self.buffer, self.received_at = b'', time.monotonic()
        try:
            self.connection.request('GET', path, headers={
                'Authorization': 'Basic ' + base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode(),
                'Connection': 'close',
            })
            self.socket = self.connection.sock
            self.response = self.connection.getresponse()
            if self.response.status != 200:
                raise ValueError(f'Stream returned {self.response.status}')
        except BaseException:
            if hasattr(self, 'response'):
                self.response.close()
            self.connection.close()
            raise

    def event(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('No event before deadline')
            self.socket.settimeout(remaining)
            block = self.response.read1(65536)
            self.received_at = time.monotonic()
            if not block:
                if self.buffer:
                    raise ValueError('Truncated stream event')
                return None, self.received_at
            self.buffer += block
            if len(self.buffer) > 1_048_576:
                raise ValueError('Unbounded event frame')
        line, _, self.buffer = self.buffer.partition(b'\n')
        return json.loads(line), self.received_at

    def close(self):
        if self.closed.is_set():
            return
        self.closed.set()
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.response.close()
        self.connection.close()


def measure_spacing(base, *, probe_path=PROBE_PATH, auth=AUTH):
    started = time.monotonic()
    stream = Stream(base, probe_path + '/spacing', auth=auth)
    events, arrivals = [], []
    try:
        while True:
            event, when = stream.event()
            if event is None:
                break
            if event.get('type') == 'chunk':
                events.append(event['index'])
                arrivals.append(when)
    finally:
        stream.close()
    return {'started': started, 'indices': events, 'arrivals': arrivals}


def _probe(http, base, path, kind, record):
    started = time.monotonic()
    try:
        response = http.get(base + path, timeout=2)
        record['probes'].append({
            'kind': kind, 'started': started, 'ms': (time.monotonic() - started) * 1000,
            'status': response.status_code, 'retry_after': response.headers.get('Retry-After'),
        })
    except Exception as error:
        record['errors'].append(f'{kind}:{type(error).__name__}')


@contextmanager
def saturated_streams(base, *, probe_path=PROBE_PATH, auth=AUTH):
    record = {'opened': [], 'closed': 0, 'probes': [], 'events': [], 'errors': []}
    streams, readers = [], []
    stop = threading.Event()
    prober = None

    def drain(stream, index):
        try:
            while not stream.closed.is_set():
                event, arrival = stream.event()
                if event is None:
                    if not stream.closed.is_set():
                        record['errors'].append(f'stream-{index}:unexpected_eof')
                    return
                record['events'].append({'stream': index, 'type': event['type'], 'arrival': arrival})
        except Exception as error:
            if not stream.closed.is_set():
                record['errors'].append(f'stream-{index}:{type(error).__name__}')

    def probes():
        with client(auth=auth) as http:
            deadline, next_extra = record['started'], record['started']
            while not stop.wait(max(0, deadline - time.monotonic())):
                _probe(http, base, probe_path + '/echo', 'short', record)
                if time.monotonic() >= next_extra:
                    _probe(http, base, probe_path + '/active', 'excess', record)
                    next_extra += 5
                deadline += 1

    try:
        for index, kind in enumerate(('active', 'idle', 'idle', 'idle')):
            stream = Stream(base, probe_path + '/' + kind, auth=auth)
            streams.append(stream)
            first, _ = stream.event()
            if first is None or first['type'] != ('chunk' if kind == 'active' else 'heartbeat'):
                raise ValueError('Saturation stream did not become active')
            record['opened'].append(kind)
            reader = threading.Thread(target=drain, args=(stream, index), name=f'native-stream-{index}', daemon=True)
            reader.start()
            readers.append(reader)
        record['started'] = time.monotonic()
        prober = threading.Thread(target=probes, name='native-saturation-probes', daemon=True)
        prober.start()
        yield record
    finally:
        record['ended'] = time.monotonic()
        stop.set()
        if prober is not None:
            prober.join(3)
            if prober.is_alive():
                record['errors'].append('probe_thread_alive')
        for stream in streams:
            try:
                stream.close()
                record['closed'] += 1
            except Exception as error:
                record['errors'].append(f'close:{type(error).__name__}')
        for reader in readers:
            reader.join(3)
            if reader.is_alive():
                record['errors'].append('reader_thread_alive')
        diagnostics = probe_path.split('/apps/', 1)[0] + '/api/diagnostics'
        with client(auth=auth) as http:
            deadline = time.monotonic() + 3
            while True:
                response = http.get(base + diagnostics, timeout=2)
                if response.status_code != 200:
                    record['errors'].append('diagnostics_failed')
                    break
                record['after'] = response.json()
                if record['after'].get('streamInFlightCount') == 0:
                    break
                if time.monotonic() >= deadline:
                    record['errors'].append('streams_not_reclaimed')
                    break
                time.sleep(0.02)


def validate_transport(payload):
    try:
        spacing, saturation = payload['spacing'], payload['saturation']
        times = spacing['arrivals']
        if len(times) != 8 or spacing['indices'] != list(range(8)):
            raise ValueError('Missing stream frames')
        started = finite(spacing['started'])
        times = [finite(value) for value in times]
        gaps = [(right - left) * 1000 for left, right in zip(times, times[1:])]
        first, gap_p95 = (times[0] - started) * 1000, percentile(gaps, 0.95)
        if first < 0 or first > 200 or gap_p95 > 150:
            raise ValueError('Buffered or late stream delivery')
        if saturation['opened'] != ['active', 'idle', 'idle', 'idle'] or saturation['closed'] != 4 or saturation['errors']:
            raise ValueError('Incomplete saturation or cleanup')
        start, end = finite(saturation['started']), finite(saturation['ended'])
        duration = end - start
        if duration <= 0:
            raise ValueError('Invalid saturation interval')
        short, excess = [], []
        for row in saturation['probes']:
            if not start <= finite(row['started']) <= end:
                raise ValueError('Probe outside saturation interval')
            elapsed = finite(row['ms'])
            if row['kind'] == 'short':
                if row['status'] != 200 or elapsed >= 100:
                    raise ValueError('Short requests failed or reached 100ms')
                short.append(row)
            elif row['kind'] == 'excess':
                if row['status'] != 503 or row['retry_after'] != '2':
                    raise ValueError('Missing excess-stream rejection')
                excess.append(row)
            else:
                raise ValueError('Unknown saturation probe')
        if len(short) < max(1, math.floor(duration)) or len(excess) < max(1, math.floor(duration / 5)):
            raise ValueError('Missing saturation probes')
        stream_count = saturation['after']['streamInFlightCount']
        short_count = saturation['after']['shortInFlightCount']
        if (type(stream_count) is not int or stream_count != 0
                or type(short_count) is not int or short_count not in {0, 1}):
            raise ValueError('Admission resources were not returned')
        return {'first_event_ms': first, 'spacing_p95_ms': gap_p95,
                'short_probes': len(short), 'excess_probes': len(excess)}
    except (KeyError, TypeError) as error:
        raise ValueError('Incomplete transport measurement') from error
