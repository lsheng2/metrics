from copy import deepcopy

import pytest


def page_payload():
    from scripts.validation.windows_host_samples import ARMS, MODES, PAGE_KEYS

    return {
        'pages': {
            mode: {
                page: {
                    arm: [
                        {'block': block, 'sample': sample, 'ms': 10.0 if arm == 'baseline' else 11.0,
                         'html_ms': 2.0, 'status': 200,
                         'assets': [{'url': '/static/app.js', 'status': 200, 'bytes': 42, 'sha256': 'a' * 64}]}
                        for block in range(4) for sample in range(40)
                    ] for arm in ARMS
                } for page in PAGE_KEYS
            } for mode in MODES
        },
    }


def test_page_validator_recomputes_all_cells_from_raw_samples():
    from scripts.validation.windows_host_samples import validate_pages

    result = validate_pages(page_payload())
    assert len(result) == 24
    assert all(row['ratio'] == 1.1 for row in result)


@pytest.mark.parametrize('mutation', [
    'threshold', 'missing_sample', 'duplicate_sample', 'empty_assets',
    'wrong_asset', 'failed_asset', 'nan', 'missing_page',
])
def test_page_validator_refuses_false_pass_or_incomplete_measurement(mutation):
    from scripts.validation.windows_host_samples import validate_pages

    payload = page_payload()
    samples = payload['pages']['seq']['home']['candidate']
    if mutation == 'threshold':
        for sample in samples[-9:]:
            sample['ms'] = 20.0
    elif mutation == 'missing_sample':
        samples.pop()
    elif mutation == 'duplicate_sample':
        samples[-1] = deepcopy(samples[0])
    elif mutation == 'empty_assets':
        samples[0]['assets'] = []
    elif mutation == 'wrong_asset':
        samples[0]['assets'][0]['sha256'] = 'b' * 64
    elif mutation == 'failed_asset':
        samples[0]['assets'][0]['status'] = 404
    elif mutation == 'nan':
        samples[0]['ms'] = float('nan')
    else:
        del payload['pages']['c4']['draft_edit']
    payload['result'] = 'PASS'
    with pytest.raises(ValueError):
        validate_pages(payload)


def test_percentile_uses_original_nearest_rank_not_interpolation():
    from scripts.validation.windows_host_samples import percentile

    assert percentile([10.0] * 152 + [20.0] * 8, 0.95) == 10.0
    assert percentile([10.0] * 151 + [20.0] * 9, 0.95) == 20.0


def test_arm_cleanup_attempts_every_owner_and_refuses_unknown_exit_status():
    from scripts.validation.windows_host_processes import stop_arms
    from scripts.service_lifecycle_engine.models import StopResult

    class Engine:
        def __init__(self):
            self.stopped = []

        def stop_service(self, name, *, graceful_timeout_seconds):
            self.stopped.append((name, graceful_timeout_seconds))
            return StopResult(name, 1234, 123, True, False, 'stop_command',
                              exit_code=None if name == 'candidate' else 0)

    engine = Engine()
    receipt = stop_arms(engine, ['baseline', 'candidate'])
    assert engine.stopped == [('candidate', 15), ('baseline', 15)]
    assert receipt['normal'] is False
    assert receipt['services']['baseline']['exit_code'] == 0
    assert receipt['services']['candidate']['exit_code'] is None


def test_measurement_window_refuses_overlap_and_detects_source_drift(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    identity = {'head': 'before'}
    monkeypatch.setattr(environment, 'source_snapshot', lambda root: dict(identity))
    monkeypatch.setattr(environment, 'machine_snapshot', lambda: {'processes': [], 'cpu': {'idle': 1, 'kernel': 2, 'user': 3}})
    run = tmp_path / 'run'
    run.mkdir()
    with pytest.raises(ValueError, match='source'):
        with environment.MeasurementWindow(tmp_path, run, tmp_path) as window:
            with pytest.raises(FileExistsError):
                with environment.MeasurementWindow(tmp_path, run, tmp_path):
                    pass
            identity['head'] = 'changed'
    assert not (tmp_path / 'HEAVY_RUN_ACTIVE').exists()
    assert window.record['source_before'] != window.record['source_after']


def test_measurement_window_never_removes_another_owners_guard(tmp_path, monkeypatch):
    from scripts.validation import windows_host_environment as environment

    monkeypatch.setattr(environment, 'source_snapshot', lambda root: {'head': 'unchanged'})
    monkeypatch.setattr(environment, 'machine_snapshot', lambda: {'processes': [], 'cpu': {'idle': 1, 'kernel': 2, 'user': 3}})
    run = tmp_path / 'run'
    run.mkdir()
    with pytest.raises(ValueError, match='guard'):
        with environment.MeasurementWindow(tmp_path, run, tmp_path):
            (tmp_path / 'HEAVY_RUN_ACTIVE').write_text('{"id":"different-owner"}', encoding='utf-8')
    assert (tmp_path / 'HEAVY_RUN_ACTIVE').exists()


def test_windows_machine_snapshot_contains_real_process_and_cpu_counters():
    import os
    from scripts.validation.windows_host_environment import machine_snapshot

    snapshot = machine_snapshot()
    assert any(row['pid'] == os.getpid() and row['threads'] > 0 for row in snapshot['processes'])
    assert snapshot['cpu']['kernel'] >= snapshot['cpu']['idle'] >= 0
    assert snapshot['cpu']['user'] >= 0


def transport_payload():
    return {
        'spacing': {'started': 100.0, 'arrivals': [100.05 + i / 10 for i in range(8)], 'indices': list(range(8))},
        'saturation': {
            'started': 200.0, 'ended': 210.0,
            'opened': ['active', 'idle', 'idle', 'idle'], 'closed': 4, 'errors': [],
            'after': {'streamInFlightCount': 0, 'shortInFlightCount': 1},
            'probes': [
                {'kind': 'short', 'started': 200.0 + i, 'ms': 20.0, 'status': 200}
                for i in range(10)
            ] + [
                {'kind': 'excess', 'started': 200.0 + i, 'ms': 20.0, 'status': 503, 'retry_after': '2'}
                for i in (0, 5)
            ],
        },
    }


def test_transport_validator_uses_observed_times_statuses_and_resource_counts():
    from scripts.validation.windows_host_transport import validate_transport

    result = validate_transport(transport_payload())
    assert result['first_event_ms'] == pytest.approx(50)
    assert result['spacing_p95_ms'] == pytest.approx(100)


@pytest.mark.parametrize('mutation', ['late', 'buffered', 'short_failed', 'short_slow', 'missing_probe', 'wrong_retry', 'leak'])
def test_transport_validator_refuses_incomplete_or_slow_observations(mutation):
    from scripts.validation.windows_host_transport import validate_transport

    payload = transport_payload()
    if mutation == 'late':
        payload['spacing']['started'] = 99.0
    elif mutation == 'buffered':
        payload['spacing']['arrivals'][-1] += 0.5
    elif mutation == 'short_failed':
        payload['saturation']['probes'][0]['status'] = 503
    elif mutation == 'short_slow':
        payload['saturation']['probes'][0]['ms'] = 100.0
    elif mutation == 'missing_probe':
        payload['saturation']['probes'] = payload['saturation']['probes'][-2:]
    elif mutation == 'wrong_retry':
        payload['saturation']['probes'][-1]['retry_after'] = '3'
    else:
        payload['saturation']['after']['streamInFlightCount'] = 1
    payload['result'] = 'PASS'
    with pytest.raises(ValueError):
        validate_transport(payload)


def test_sampler_includes_distinct_assets_and_excludes_parse_time(monkeypatch):
    from types import SimpleNamespace
    from scripts.validation import windows_host_samples as samples

    html = '<link href="/static/a.css"><script src="/static/b.js"></script><img src="/static/i.png"><img src="/static/i.png">'
    seen = []

    class Http:
        def get(self, url):
            seen.append(url)
            return SimpleNamespace(status_code=200, text=html if url.endswith('/') else '', content=b'asset')

    times = iter([0.0, 0.02, 1.0, 1.03])
    monkeypatch.setattr(samples.time, 'perf_counter', lambda: next(times))
    measured = samples.sample_page(Http(), 'http://127.0.0.1:1234', '/')
    assert measured['ms'] == pytest.approx(50)
    assert measured['html_ms'] == pytest.approx(20)
    assert [row['url'] for row in measured['assets']] == ['/static/a.css', '/static/b.js', '/static/i.png']
    assert len(seen) == 4


@pytest.mark.parametrize('slow', [False, True])
def test_benchmark_preserves_interleaved_recipe_and_rejects_slow_cells(tmp_path, monkeypatch, slow):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from scripts.validation import windows_host_benchmark as benchmark

    names = ('baseline', 'candidate', 'candidate_saturated')
    pages = {name: '/' + name for name in ('home', 'projects', 'project_detail', 'stage_reports', 'draft_edit', 'bug_trend')}
    calls, checks = [], []
    asset = {'url': '/static/app.js', 'status': 200, 'bytes': 42, 'sha256': 'a' * 64}

    @contextmanager
    def arms(*args, **kwargs):
        yield SimpleNamespace(
            bases={name: name for name in names},
            record={'arms': {name: {'metadata': {'pages': pages}} for name in names}},
        )

    def samples(base, path, *, count, workers, block):
        calls.append((base, path, count, workers, block))
        ms = 10.0 if base == 'baseline' else 20.0 if slow else 11.0
        return [{'block': block, 'sample': index, 'ms': ms, 'html_ms': 2.0, 'status': 200,
                 'assets': [dict(asset)]} for index in range(count)]

    @contextmanager
    def saturation(*args):
        yield transport_payload()['saturation']

    monkeypatch.setattr(benchmark, 'running_arms', arms)
    monkeypatch.setattr(benchmark, 'sanity', lambda arms: {name: {page: {'assets': [asset]} for page in pages} for name in names})
    monkeypatch.setattr(benchmark, 'run_block', samples)
    monkeypatch.setattr(benchmark, 'measure_spacing', lambda base: transport_payload()['spacing'])
    monkeypatch.setattr(benchmark, 'saturated_streams', saturation)
    monkeypatch.setattr(benchmark, 'write_json', lambda *args, **kwargs: None)
    window = SimpleNamespace(check=lambda: checks.append(True))
    if slow:
        with pytest.raises(ValueError):
            benchmark.phase(tmp_path / 'phase', tmp_path / 'python', production=False, window=window)
    else:
        result = benchmark.phase(tmp_path / 'phase', tmp_path / 'python', production=False, window=window)
        assert result['result'] == 'PASS'
    measured = [row for row in calls if row[-1] >= 0]
    assert len(measured) == 144 and len(checks) == 48
    assert all(row[2] == 40 for row in measured)
    assert [row[0] for row in measured[:6]] == [
        'baseline', 'candidate', 'candidate_saturated', 'candidate_saturated', 'candidate', 'baseline',
    ]
