"""Observed NDJSON delivery and independent stream/short-request saturation."""
import base64
from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
import json
import math
import re
import socket
import threading
import time
from types import MappingProxyType
from urllib.parse import urlsplit

from scripts.validation.windows_host_samples import AUTH, client, finite, percentile


PROBE_PATH = '/ai/apps/metrics/api/qualification'
TIMING_TOLERANCE_MS = 5.0
TAIL_LATENCY_POLICY = MappingProxyType({
    'method': 'nearest_rank',
    'quantile': 0.99,
    'p99_exclusive_ms': 100,
    'max_inclusive_ms': 200,
})


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


def _probe(http, base, path, kind, record, *, slot=None, scheduled=None):
    started = time.monotonic()
    try:
        response = http.get(base + path, timeout=2)
        ended = time.monotonic()
        record['probes'].append({
            'slot': slot, 'kind': kind, 'resource': path, 'scheduled': scheduled,
            'started': started, 'ended': ended, 'ms': (ended - started) * 1000,
            'status': response.status_code, 'retry_after': response.headers.get('Retry-After'),
            'content_sha256': hashlib.sha256(response.content).hexdigest(),
            'etag': response.headers.get('ETag'),
        })
    except Exception as error:
        ended = time.monotonic()
        record['errors'].append({
            'kind': kind, 'slot': slot, 'resource': path, 'scheduled': scheduled,
            'started': started, 'ended': ended, 'ms': (ended - started) * 1000,
            'error_type': type(error).__name__,
        })


@contextmanager
def saturated_streams(base, *, probe_path=PROBE_PATH, auth=AUTH, direct_asset_path=None):
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
            deadline, next_extra, slot = record['started'], record['started'], 0
            while not stop.wait(max(0, deadline - time.monotonic())):
                scheduled = deadline
                if direct_asset_path:
                    _probe(http, base, probe_path + '/echo', 'loop_short', record, slot=slot, scheduled=scheduled)
                    _probe(http, base, direct_asset_path, 'direct_asset', record, slot=slot, scheduled=scheduled)
                else:
                    _probe(http, base, probe_path + '/echo', 'short', record, slot=slot, scheduled=scheduled)
                if time.monotonic() >= next_extra:
                    _probe(
                        http, base, probe_path + '/active',
                        'excess_stream' if direct_asset_path else 'excess',
                        record, slot=slot, scheduled=scheduled,
                    )
                    next_extra += 5
                slot += 1
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
        stop.set()
        if prober is not None:
            prober.join(3)
            if prober.is_alive():
                record['errors'].append('probe_thread_alive')
        record['ended'] = time.monotonic()
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


def _row_interval(row):
    started = finite(row['started'])
    ended = finite(row['ended'])
    if ended < started:
        raise ValueError('Probe timing is reversed')
    if abs(finite(row['ms']) - ((ended - started) * 1000)) > TIMING_TOLERANCE_MS:
        raise ValueError('Probe elapsed time is inconsistent')
    return started, ended


def _latency_tail(rows, kind, violations):
    values = [finite(row['ms']) for row in rows]
    p99 = percentile(values, TAIL_LATENCY_POLICY['quantile'])
    worst = max(rows, key=lambda row: row['ms'])
    maximum = finite(worst['ms'])
    if p99 >= TAIL_LATENCY_POLICY['p99_exclusive_ms']:
        violations.append({
            'metric': f'{kind}_p99_ms', 'value': p99,
            'limit': TAIL_LATENCY_POLICY['p99_exclusive_ms'],
        })
    if maximum > TAIL_LATENCY_POLICY['max_inclusive_ms']:
        violations.append({
            'metric': f'{kind}_max_ms', 'slot': worst.get('slot'), 'value': maximum,
            'limit': TAIL_LATENCY_POLICY['max_inclusive_ms'],
        })
    return {'count': len(values), 'p99_ms': p99, 'max_ms': maximum}


def validate_transport(
    payload, *, spacing_events=8, require_direct_asset=False,
    direct_asset_prefix='/ai/assets/', fail_on_violation=True,
):
    try:
        spacing, saturation = payload['spacing'], payload['saturation']
        times = spacing['arrivals']
        if len(times) != spacing_events or spacing['indices'] != list(range(spacing_events)):
            raise ValueError('Missing stream frames')
        started = finite(spacing['started'])
        times = [finite(value) for value in times]
        gaps = [(right - left) * 1000 for left, right in zip(times, times[1:])]
        first, gap_p95 = (times[0] - started) * 1000, percentile(gaps, 0.95)
        violations = []
        if first < 0:
            raise ValueError('Buffered or late stream delivery')
        if first > 200:
            violations.append({'metric': 'spacing_first_event_ms', 'value': first, 'limit': 200})
        if gap_p95 > 150:
            violations.append({'metric': 'spacing_p95_ms', 'value': gap_p95, 'limit': 150})
        if fail_on_violation and violations:
            raise ValueError('Buffered or late stream delivery')
        if saturation['opened'] != ['active', 'idle', 'idle', 'idle'] or saturation['closed'] != 4 or saturation['errors']:
            raise ValueError('Incomplete saturation or cleanup')
        start, end = finite(saturation['started']), finite(saturation['ended'])
        duration = end - start
        if duration <= 0:
            raise ValueError('Invalid saturation interval')
        short, direct, excess = [], [], []
        slots = {}
        per_slot_kind_counts = {}
        for row in saturation['probes']:
            row_start, row_end = _row_interval(row)
            if not start <= row_start <= row_end <= end:
                raise ValueError('Probe outside saturation interval')
            if require_direct_asset:
                if row['kind'] not in {'loop_short', 'direct_asset', 'excess_stream'}:
                    raise ValueError('Unexpected performance probe kind')
                slot = row.get('slot')
                scheduled = finite(row.get('scheduled'))
                if type(slot) is not int or slot < 0 or abs(scheduled - (start + slot)) > 0.001:
                    raise ValueError('Probe is not bound to its scheduled slot')
                if abs(row_start - scheduled) > 0.5:
                    raise ValueError('Probe is not bound to its scheduled slot')
                if row['kind'] == 'excess_stream' and slot % 5:
                    raise ValueError('Excess probe is outside its five-second cadence')
                slots.setdefault(slot, set()).add(row['kind'])
                key = (slot, row['kind'])
                per_slot_kind_counts[key] = per_slot_kind_counts.get(key, 0) + 1
            if row['kind'] in {'short', 'loop_short'}:
                if row['status'] != 200:
                    raise ValueError('Short request failed')
                short.append(row)
            elif row['kind'] == 'direct_asset':
                digest = row.get('content_sha256')
                if (row['status'] != 200
                        or not str(row.get('resource', '')).startswith(direct_asset_prefix)
                        or not isinstance(digest, str)
                        or re.fullmatch(r'[0-9a-f]{64}', digest) is None):
                    raise ValueError('Direct runtime asset probe failed')
                direct.append(row)
            elif row['kind'] in {'excess', 'excess_stream'}:
                if row['status'] != 503 or row['retry_after'] != '2':
                    raise ValueError('Missing excess-stream rejection')
                excess.append(row)
            else:
                raise ValueError('Unknown saturation probe')
        if len(short) < max(1, math.floor(duration)) or len(excess) < max(1, math.floor(duration / 5)):
            raise ValueError('Missing saturation probes')
        if require_direct_asset:
            last_slot = math.floor(duration)
            required_slots = set(range(max(1, last_slot)))
            observed_slots = set(slots)
            if not required_slots <= observed_slots or not observed_slots <= required_slots | {last_slot}:
                raise ValueError('Missing paired direct-asset saturation probe')
            for slot in observed_slots:
                expected_kinds = {'loop_short', 'direct_asset'}
                if slot % 5 == 0:
                    expected_kinds.add('excess_stream')
                if slots[slot] != expected_kinds:
                    raise ValueError('Missing paired direct-asset saturation probe')
                if any(per_slot_kind_counts.get((slot, kind)) != 1 for kind in expected_kinds):
                    raise ValueError('Duplicate saturation probe for slot')
        stream_count = saturation['after']['streamInFlightCount']
        short_count = saturation['after']['shortInFlightCount']
        if (type(stream_count) is not int or stream_count != 0
                or type(short_count) is not int or short_count not in {0, 1}):
            raise ValueError('Admission resources were not returned')
        tails = {
            kind: _latency_tail(rows, kind, violations)
            for kind, rows in (('short', short), ('direct_asset', direct)) if rows
        }
        if fail_on_violation and violations:
            raise ValueError('Transport KPI violation')
        return {'first_event_ms': first, 'spacing_p95_ms': gap_p95,
                'short_probes': len(short), 'direct_asset_probes': len(direct), 'excess_probes': len(excess),
                'latency_tails': tails, 'violations': violations}
    except (KeyError, TypeError) as error:
        raise ValueError('Incomplete transport measurement') from error
