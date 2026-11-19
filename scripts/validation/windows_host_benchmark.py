"""Interleaved S0b page/asset and saturation measurement on the current host."""
from pathlib import Path
import time

from scripts.validation.project_full_stack_support import write_json
from scripts.validation.windows_host_processes import running_arms
from scripts.validation.windows_host_samples import (
    ARMS, BLOCKS, MODES, PAGE_KEYS, PER_BLOCK, WARMUP, Assets,
    asset_identity, client, parse_assets, run_block, sample_page, validate_pages,
)
from scripts.validation.windows_host_transport import measure_spacing, saturated_streams, validate_transport


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


def phase(root, python, *, production, window):
    root = Path(root)
    root.mkdir()
    result = {'scope': ['B3', 'B6', 'B9'], 'production': production, 'pages': {}, 'blocks': [],
              'recipe': {'blocks': BLOCKS, 'per_block': PER_BLOCK, 'warmup': WARMUP, 'modes': MODES},
              'result': 'FAIL'}
    try:
        with running_arms(root, python, production=production) as arms:
            result['processes'] = arms.record
            result['sanity'] = sanity(arms)
            metadata = {name: row['metadata'] for name, row in arms.record['arms'].items()}
            result['warmup'] = {}
            for name, base in arms.bases.items():
                result['warmup'][name] = {
                    page: run_block(base, metadata[name]['pages'][page], count=WARMUP, workers=1, block=-1)
                    for page in PAGE_KEYS
                }
                for page, samples in result['warmup'][name].items():
                    expected_assets = asset_identity(result['sanity'][name][page])
                    if any(row['status'] != 200 or asset_identity(row) != expected_assets for row in samples):
                        raise ValueError('Warmup page or assets failed')
            result['spacing'] = measure_spacing(arms.bases['candidate'])
            with saturated_streams(arms.bases['candidate_saturated']) as saturation:
                result['saturation'] = saturation
                for mode, workers in MODES.items():
                    result['pages'][mode] = {}
                    for page in PAGE_KEYS:
                        result['pages'][mode][page] = {name: [] for name in ARMS}
                        for block in range(BLOCKS):
                            window.check()
                            order = ARMS if block % 2 == 0 else tuple(reversed(ARMS))
                            for name in order:
                                started = time.monotonic()
                                samples = run_block(
                                    arms.bases[name], metadata[name]['pages'][page],
                                    count=PER_BLOCK, workers=workers, block=block,
                                )
                                result['pages'][mode][page][name].extend(samples)
                                result['blocks'].append({'mode': mode, 'page': page, 'block': block,
                                                         'arm': name, 'started': started, 'ended': time.monotonic()})
                            write_json(root / 'measurement-partial.json', result,
                                       replace=(root / 'measurement-partial.json').exists())
                            if saturation['errors']:
                                raise ValueError('Saturation stream or probe failed')
                        print(f'measured {mode}/{page} production={production}', flush=True)
            result['page_validation'] = validate_pages(result)
            result['transport_validation'] = validate_transport(result)
        result['result'] = 'PASS'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        write_json(root / 'measurement.json', result)
    return result


def run_benchmark(root, python, window):
    return {
        'development': phase(Path(root) / 'development', python, production=False, window=window),
        'production': phase(Path(root) / 'production', python, production=True, window=window),
    }
