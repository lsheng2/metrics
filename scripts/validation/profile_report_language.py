import argparse
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.profile_report_reads import AUTH, GitMeter, denied_network, nearest_rank_p95, validate_output_dir
from scripts.validation.project_full_stack_support import require_owned_run_dir, write_json
from scripts.validation.report_read_identity import preflight_run_manifest, source_identity


def main():
    parser = argparse.ArgumentParser(description='Measure language POST without hiding redirect GET cost.')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run = require_owned_run_dir(args.run_dir)
    manifest = preflight_run_manifest(run)
    output = validate_output_dir(run, args.output_dir)
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_week_settings'
    import django
    django.setup()
    from django.conf import settings
    from django.test import Client
    from django.urls import reverse
    from project_management.storage.git import GitRunner

    with denied_network() as network:
        client = Client(enforce_csrf_checks=True)
        target = manifest['routes']['project_stage_reports']
        if client.get(target, **AUTH).status_code != 200:
            raise ValueError('Cannot load CSRF seed from the owned workbench.')
        csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
        samples = []
        for index in range(20):
            language = 'zh-hans' if index % 2 == 0 else 'en'
            meter, original = GitMeter(), GitRunner.run

            def measured(runner, arguments, **kwargs):
                return meter.run(original, runner, arguments, kwargs)

            with patch.object(GitRunner, 'run', measured):
                start = perf_counter()
                response = client.post(reverse('ui_web:project_language'),
                                       {'language': language, 'next': target},
                                       HTTP_X_CSRFTOKEN=csrf, **AUTH)
                seconds = perf_counter() - start
            samples.append({
                'seconds': seconds, 'status': response.status_code, 'git_calls': meter.calls,
                'language': language, 'cookie_matches': response.cookies[settings.LANGUAGE_COOKIE_NAME].value == language,
                'same_target': response.get('Location') == target,
            })
    p95 = nearest_rank_p95(item['seconds'] for item in samples)
    passed = p95 <= 0.15 and not network and all(
        item['status'] == 302 and not item['git_calls'] and item['cookie_matches'] and item['same_target']
        for item in samples
    )
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / f'language-post-{uuid4()}.json', {
        'samples': samples, 'p95_seconds': p95, 'passed': passed, 'source': source_identity(),
        'scope': 'POST only; redirect GET and completed browser repaint are separate evidence',
    })
    print(json.dumps({'p95_seconds': p95, 'passed': passed}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
