import json
from pathlib import Path
import sys
from urllib.parse import urlparse


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_host.tests.serve_test_entry import main


def configure(temp):
    endpoint = sys.argv[4]
    if urlparse(endpoint).hostname != '127.0.0.1':
        raise ValueError('Synthetic model must be loopback')
    return {
        'METRICS_AI_MODEL_BASE_URL': endpoint,
        'METRICS_AI_MODEL_NAME': 'scripted',
        'METRICS_AI_MODEL_API_KEY': 'synthetic-browser-key',
        'AI_HOST_ALLOW_ANONYMOUS_APPROVAL': True,
    }


def prepare():
    from datetime import datetime, timezone
    from bug_metrics.models import BugTrendBucketIssue
    from ui_web.tests.workbench_view_test_support import WorkbenchViewTestSupport

    helper = WorkbenchViewTestSupport()
    scope, run, bucket = helper._seed_trend_data()
    scope.name = 'Synthetic Workbench'
    scope.save()
    BugTrendBucketIssue.objects.create(
        scope=scope, bucket=bucket, calculation_run=run,
        series_name='new_critical_high', issue_key='SAMPLE-1',
        summary='Synthetic evidence item', status='Open', severity_value='P1-Critical',
        component_value='sample', owner_value='Synthetic user',
        created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    unresolved = helper._bound_scope('missing-synthetic-profile', 'jira')
    print(json.dumps({'event': 'browser_scopes', 'scope': scope.id, 'unresolved': unresolved.id}), flush=True)


if __name__ == '__main__':
    raise SystemExit(main(configure=configure, prepare=prepare))
