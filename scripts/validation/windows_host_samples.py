"""S0b's page-plus-assets sampling recipe and strict raw-sample acceptance."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html import unescape
from html.parser import HTMLParser
import math
import re
import threading
import time
from urllib.parse import urlsplit

import httpx


PAGE_KEYS = ('home', 'projects', 'project_detail', 'stage_reports', 'draft_edit', 'bug_trend')
ARMS = ('baseline', 'candidate', 'candidate_saturated')
MODES = {'seq': 1, 'c4': 4}
BLOCKS, PER_BLOCK, WARMUP = 4, 40, 10
AUTH = ('alice', 'wonder')
ASSET_RE = re.compile(r'<(link|script|img)\b[^>]*?\b(href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        value = attributes.get('href') if tag == 'link' else attributes.get('src') if tag in {'script', 'img'} else None
        if value and value.startswith('/static/'):
            path = value.split('#')[0]
            if path not in self.paths:
                self.paths.append(path)


def parse_assets(html):
    paths = []
    for tag, attribute, value in ASSET_RE.findall(html):
        tag, attribute = tag.lower(), attribute.lower()
        if (tag == 'link' and attribute == 'href') or (tag in {'script', 'img'} and attribute == 'src'):
            value = unescape(value).split('#')[0]
            if value.startswith('/static/') and value not in paths:
                paths.append(value)
    return paths


def finite(value, *, positive=False):
    if type(value) not in {int, float} or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError('Invalid measurement')
    return value


def percentile(values, quantile):
    if not values:
        raise ValueError('Empty sample set')
    ordered = sorted(finite(value) for value in values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


def client(*, auth=AUTH):
    return httpx.Client(auth=auth, timeout=60, trust_env=False, verify=False)


def sample_page(http, base, path):
    if urlsplit(base).hostname != '127.0.0.1' or not path.startswith('/'):
        raise ValueError('Only an owned loopback page can be measured')
    started = time.perf_counter()
    response = http.get(base + path)
    html_seconds = time.perf_counter() - started
    assets = parse_assets(response.text)
    payloads = []
    assets_started = time.perf_counter()
    for asset in assets:
        result = http.get(base + asset)
        payloads.append((asset, result.status_code, result.content))
    assets_seconds = time.perf_counter() - assets_started
    # Hashing and parsing are outside the original HTTP timing window.
    return {
        'ms': (html_seconds + assets_seconds) * 1000,
        'html_ms': html_seconds * 1000, 'status': response.status_code,
        'assets': [{'url': path, 'status': status, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                   for path, status, data in payloads],
    }


def run_block(base, path, *, count, workers, block):
    counter, lock = iter(range(count)), threading.Lock()

    def worker():
        rows = []
        with client() as http:
            while True:
                with lock:
                    index = next(counter, None)
                if index is None:
                    return rows
                rows.append({'block': block, 'sample': index, **sample_page(http, base, path)})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = [pool.submit(worker) for _ in range(workers)]
        return [row for result in results for row in result.result()]


def asset_identity(sample):
    assets = sample.get('assets')
    if not assets:
        raise ValueError('Page has no measured assets')
    result = {}
    for asset in assets:
        url, digest = asset['url'], asset['sha256']
        if (not url.startswith('/static/') or url in result or asset['status'] != 200
                or type(asset['bytes']) is not int or asset['bytes'] <= 0
                or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('Missing, failed or invalid asset sample')
        result[url] = (digest, asset['bytes'])
    return result


def validate_cell(samples, *, blocks=BLOCKS, per_block=PER_BLOCK):
    expected = {(block, sample) for block in range(blocks) for sample in range(per_block)}
    if len(samples) != len(expected) or {(row['block'], row['sample']) for row in samples} != expected:
        raise ValueError('Missing or duplicate samples')
    assets = asset_identity(samples[0])
    for row in samples:
        if row['status'] != 200 or asset_identity(row) != assets:
            raise ValueError('Page or asset identity changed during measurement')
        if finite(row['html_ms']) > finite(row['ms'], positive=True):
            raise ValueError('Invalid component timings')
    return percentile([row['ms'] for row in samples], 0.95), assets


def validate_pages(payload, *, blocks=BLOCKS, per_block=PER_BLOCK):
    try:
        pages = payload['pages']
        if set(pages) != set(MODES):
            raise ValueError('Missing measurement mode')
        rows = []
        for mode in MODES:
            if set(pages[mode]) != set(PAGE_KEYS):
                raise ValueError('Missing required page')
            for page in PAGE_KEYS:
                arms = pages[mode][page]
                if set(arms) != set(ARMS):
                    raise ValueError('Missing required arm')
                baseline, baseline_assets = validate_cell(arms['baseline'], blocks=blocks, per_block=per_block)
                for arm in ARMS[1:]:
                    candidate, assets = validate_cell(arms[arm], blocks=blocks, per_block=per_block)
                    ratio = candidate / baseline
                    if assets != baseline_assets or ratio > 1.2:
                        raise ValueError(f'{mode}/{page}/{arm}: asset mismatch or p95 exceeds 1.2x')
                    rows.append({'mode': mode, 'page': page, 'arm': arm, 'ratio': ratio,
                                 'baseline_p95_ms': baseline, 'candidate_p95_ms': candidate})
        return rows
    except (KeyError, TypeError, ZeroDivisionError) as error:
        raise ValueError('Incomplete measurement payload') from error
