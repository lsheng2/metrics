import argparse
from copy import deepcopy
from datetime import UTC, datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.profile_report_reads import AUTH, GitMeter, denied_network, nearest_rank_p95, validate_output_dir
from scripts.validation.project_full_stack_support import require_owned_run_dir, write_json
from scripts.validation.report_read_identity import environment_identity, preflight_run_manifest, source_identity


class EditorIdentity(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.identity = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'article' and 'data-report-editor' in values:
            self.identity = values


def save_payload(seed, current, sample):
    payload = dict(seed)
    payload.update(command_id=str(uuid4()), expected_revision=str(current['revision']),
                   expected_revision_hash=current['revision_hash'])
    edits = deepcopy(json.loads(payload['authored_edits']))
    if len(edits) != 1 or edits[0]['kind'] != 'note' or edits[0]['target']['scope'] != 'daily_note':
        raise ValueError('Use a single synthetic daily note seed.')
    edit = edits[0]
    note_id = str(UUID(edit['target']['note_id']))
    edit['expected_original_hash'] = current['current_note_hashes'][note_id]
    content = edit['fragment']['blocks'][0]['content'][0]
    content['text'] = f'Performance proof: manual note retained. AR: @Bob verify read latency. Sample {sample:02d}.'
    content['foreground'] = ('#aa0000', '#0055aa', '#008000')[sample % 3]
    payload['authored_edits'] = json.dumps(edits, separators=(',', ':'))
    return payload


def main():
    parser = argparse.ArgumentParser(description='Measure real Save requests against one owned synthetic draft.')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--draft-id', required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--resume-receipt', type=Path)
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.samples <= 20:
        raise ValueError('Save sample count must be between 1 and 20.')
    run = require_owned_run_dir(args.run_dir)
    manifest = preflight_run_manifest(run)
    output = validate_output_dir(run, args.output_dir)
    seed_path = args.seed.resolve(strict=True)
    if not seed_path.is_relative_to((run / 'evidence').resolve()):
        raise ValueError('Save seed must be from this synthetic evidence directory.')
    seed = json.loads(seed_path.read_text(encoding='utf-8'))
    current = seed['metrics'][-1]
    if args.resume_receipt is not None:
        receipt_path = args.resume_receipt.resolve(strict=True)
        if not receipt_path.is_relative_to((run / 'evidence').resolve()):
            raise ValueError('Resume receipt must be from this synthetic run.')
        resumed = json.loads(receipt_path.read_text(encoding='utf-8'))
        if resumed['run_dir'] != str(run) or resumed['draft_id'] != str(UUID(args.draft_id)):
            raise ValueError('Resume receipt belongs to a different draft.')
        current = resumed['current']
    draft_id = str(UUID(args.draft_id))
    base = manifest['routes']['project_stage_reports'] + f'drafts/{draft_id}/'
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_week_settings'
    import django
    django.setup()
    from django.conf import settings
    from django.test import Client
    from project_management.storage.git import GitRunner

    started = datetime.now(UTC).isoformat()
    source_before = source_identity()
    client = Client(enforce_csrf_checks=True)
    records = []
    error = None
    with denied_network() as attempts:
        response = client.get(base, **AUTH)
        identity = EditorIdentity(response.content.decode('utf-8')).identity
        if (response.status_code != 200 or identity.get('data-revision') != str(current['revision'])
                or identity.get('data-revision-hash') != current['revision_hash']):
            raise ValueError('Seed no longer describes the current synthetic editor.')
        csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
        for index in range(args.samples):
            payload = save_payload(seed['fields'], current, index + 1)
            meter, original = GitMeter(), GitRunner.run

            def measured(runner, arguments, **kwargs):
                return meter.run(original, runner, arguments, kwargs)

            before = perf_counter()
            try:
                with patch.object(GitRunner, 'run', measured):
                    response = client.post(base + 'save/', payload, HTTP_X_CSRFTOKEN=csrf,
                                           HTTP_ACCEPT='application/json', **AUTH)
                elapsed = perf_counter() - before
                data = response.json()
                records.append({
                    'index': index, 'seconds': elapsed, 'status': response.status_code,
                    'revision': data.get('revision'), 'revision_hash': data.get('revision_hash'),
                    'git_calls': meter.calls, 'git_seconds': meter.seconds,
                })
                if response.status_code != 200 or data.get('revision') != current['revision'] + 1:
                    raise ValueError('Save failed or returned an unexpected revision.')
                current = data
            except Exception as failure:
                error = type(failure).__name__
                break
        final_page = client.get(base, **AUTH)
        final_html = final_page.content.decode('utf-8')
        preserved = (final_page.status_code == 200
                     and f'Sample {len(records):02d}.' in final_html
                     and EditorIdentity(final_html).identity.get('data-revision') == str(current['revision']))
    source_after = source_identity()
    p95 = nearest_rank_p95(row['seconds'] for row in records)
    gates = {
        'samples': len(records) == 20, 'success': error is None and all(row['status'] == 200 for row in records),
        'save_p95': p95 is not None and p95 <= 2,
        'reopened': preserved, 'no_network': not attempts,
        'stable_runtime': source_before['runtime_source_digest'] == source_after['runtime_source_digest'],
    }
    receipt = {
        'started_at': started, 'run_dir': str(run), 'draft_id': draft_id,
        'samples': records, 'p95_seconds': p95, 'gates': gates, 'passed': all(gates.values()),
        'error': error, 'current': current, 'source_before': source_before, 'source_after': source_after,
        'environment': environment_identity(output, manifest),
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / f'save-{uuid4()}.json', receipt)
    print(json.dumps({'p95_seconds': p95, 'gates': gates, 'passed': all(gates.values())}), flush=True)
    return 0 if all(gates.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
