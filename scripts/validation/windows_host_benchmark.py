"""Interleaved S0b page/asset and saturation measurement on the current host."""
from pathlib import Path
import re
import time

from scripts.validation.project_full_stack_support import write_json
from scripts.validation.windows_host_processes import running_arms
from scripts.validation.windows_host_samples import (
    ARMS, BLOCKS, MODES, PAGE_KEYS, PER_BLOCK, WARMUP, Assets,
    asset_identity, client, parse_assets, run_block, sample_page, validate_pages,
)
from scripts.validation.windows_host_transport import measure_spacing, saturated_streams, validate_transport


DEFAULT_RECIPE = {'blocks': BLOCKS, 'per_block': PER_BLOCK, 'warmup': WARMUP,
                  'spacing_events': 8, 'require_direct_asset': False}
AI_ASSET_RE = re.compile(r'["\'](/ai/assets/[^"\']+)["\']')


def discover_direct_asset(base):
    with client() as http:
        response = http.get(base + '/ai/')
        if response.status_code != 200:
            raise ValueError('Runtime asset page is unavailable')
        matches = AI_ASSET_RE.findall(response.text)
    if not matches:
        raise ValueError('No direct runtime asset was discovered')
    return matches[0]


def sanity(arms):
    records = {}
    for name, base in arms.bases.items():
        metadata = arms.record['arms'][name]['metadata']
        pages = metadata['pages']
        samples = {}
        with client() as http:
            for page, path in pages.items():
                html = http.get(base + path)
                if html.status_code != 200:
                    raise ValueError('A required baseline page is unavailable')
                reference = Assets()
                reference.feed(html.text)
                if reference.paths != parse_assets(html.text):
                    raise ValueError('Original selector differs from structured asset parser')
                samples[page] = sample_page(http, base, path)
                asset_identity(samples[page])
            first_asset = samples['home']['assets'][0]['url']
            unauthenticated = http.get(base + first_asset, auth=None)
            if unauthenticated.status_code != (200 if name == 'baseline' else 401):
                raise ValueError('Static authentication posture differs from the signed baseline')
            if http.get(base + pages['home'], auth=None).status_code != 401:
                raise ValueError('Page authentication posture differs from the signed baseline')
        records[name] = samples
    for page in PAGE_KEYS:
        baseline = asset_identity(records['baseline'][page])
        if any(asset_identity(records[name][page]) != baseline for name in ARMS[1:]):
            raise ValueError('Baseline/candidate page assets differ')
    return records


def phase(root, python, *, production, window, recipe=None):
    recipe = {**DEFAULT_RECIPE, **(recipe or {})}
    blocks, per_block, warmup = recipe['blocks'], recipe['per_block'], recipe['warmup']
    root = Path(root)
    root.mkdir()
    result = {'scope': ['B3', 'B6', 'B9'], 'production': production, 'pages': {}, 'blocks': [],
              'recipe': {**recipe, 'modes': MODES},
              'result': 'FAIL'}
    try:
        with running_arms(root, python, production=production, spacing_events=recipe['spacing_events']) as arms:
            result['processes'] = arms.record
            result['sanity'] = sanity(arms)
            metadata = {name: row['metadata'] for name, row in arms.record['arms'].items()}
            result['warmup'] = {}
            for name, base in arms.bases.items():
                result['warmup'][name] = {
                    page: run_block(base, metadata[name]['pages'][page], count=warmup, workers=1, block=-1)
                    for page in PAGE_KEYS
                }
                for page, samples in result['warmup'][name].items():
                    expected_assets = asset_identity(result['sanity'][name][page])
                    if any(row['status'] != 200 or asset_identity(row) != expected_assets for row in samples):
                        raise ValueError('Warmup page or assets failed')
            result['spacing'] = measure_spacing(arms.bases['candidate'])
            direct_asset = discover_direct_asset(arms.bases['candidate_saturated']) if recipe['require_direct_asset'] else None
            with saturated_streams(arms.bases['candidate_saturated'], direct_asset_path=direct_asset) as saturation:
                result['saturation'] = saturation
                for mode, workers in MODES.items():
                    result['pages'][mode] = {}
                    for page in PAGE_KEYS:
                        result['pages'][mode][page] = {name: [] for name in ARMS}
                        for block in range(blocks):
                            window.check()
                            order = ARMS if block % 2 == 0 else tuple(reversed(ARMS))
                            for name in order:
                                started = time.monotonic()
                                samples = run_block(
                                    arms.bases[name], metadata[name]['pages'][page],
                                    count=per_block, workers=workers, block=block,
                                )
                                result['pages'][mode][page][name].extend(samples)
                                result['blocks'].append({'mode': mode, 'page': page, 'block': block,
                                                         'arm': name, 'started': started, 'ended': time.monotonic()})
                            write_json(root / 'measurement-partial.json', result,
                                       replace=(root / 'measurement-partial.json').exists())
                            if saturation['errors']:
                                raise ValueError('Saturation stream or probe failed')
                        print(f'measured {mode}/{page} production={production}', flush=True)
            result['page_validation'] = validate_pages(result, blocks=blocks, per_block=per_block)
            result['transport_validation'] = validate_transport(
                result, spacing_events=recipe['spacing_events'], require_direct_asset=recipe['require_direct_asset'],
            )
        result['result'] = 'PASS'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        write_json(root / 'measurement.json', result)
    return result


def run_benchmark(root, python, window, *, recipe=None):
    return {
        'development': phase(Path(root) / 'development', python, production=False, window=window, recipe=recipe),
        'production': phase(Path(root) / 'production', python, production=True, window=window, recipe=recipe),
    }
