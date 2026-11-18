import importlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai_host.tests.serve_test_entry import main


def configure(temp):
    from unittest.mock import patch

    config = json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))
    for field in ('model_url', 'grafana_url'):
        if urlsplit(config[field]).hostname != '127.0.0.1':
            raise ValueError('Publication fixture endpoints must be loopback.')
    os.environ['METRICS_BASIC_AUTH_USERS'] = json.dumps({config['username']: config['password']})
    with patch('environs.Env.read_env', lambda *args, **kwargs: None):
        importlib.reload(importlib.import_module('metrics.settings.defaults_metrics'))
        production = importlib.import_module('metrics.settings.production')
    values = {key: value for key, value in vars(production).items() if key.isupper()}
    values.update({
        'DEBUG': False,
        'ALLOWED_HOSTS': ['127.0.0.1'],
        'DATABASES': {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(temp / 'catalog.sqlite3')}},
        'STATIC_ROOT': temp / 'static',
        'METRICS_PROJECT_RUN_ENABLED': True,
        'METRICS_PROJECT_ARCHIVE_AUTHOR_NAME': 'Synthetic Publication Test',
        'METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL': 'synthetic@example.test',
        'METRICS_AI_MODEL_BASE_URL': config['model_url'],
        'METRICS_AI_MODEL_NAME': 'scripted',
        'METRICS_AI_MODEL_API_KEY': 'synthetic-publication-key',
        'METRICS_AI_GRAFANA_BASE_URL': config['grafana_url'],
        'METRICS_AI_GRAFANA_USERNAME': config['username'],
        'METRICS_AI_GRAFANA_PASSWORD': config['password'],
    })
    assert not values.get('AI_HOST_ALLOW_ANONYMOUS_APPROVAL', False)
    return values


def prepare():
    from dataclasses import asdict
    from django.conf import settings
    from django.core.management import call_command
    from ai_host.management.commands.serve import Command
    from bug_metrics.tests.ai_publication_fixtures import seed_publication_data

    original = Command._with_runtime_stop_result

    def observed_stop(command, outcome, stop_result):
        result = original(command, outcome, stop_result)
        print(json.dumps({'event': 'publication_stop', 'outcome': asdict(result)}), flush=True)
        return result

    Command._with_runtime_stop_result = observed_stop
    call_command('collectstatic', interactive=False, verbosity=0)
    scope, run = seed_publication_data()
    print(json.dumps({
        'event': 'publication_fixture',
        'scope': scope.id,
        'calculation_run': str(run.id),
        'database': settings.DATABASES['default']['NAME'],
        'settings': 'metrics.settings.production',
        'debug': settings.DEBUG,
        'anonymous_approval': settings.AI_HOST_ALLOW_ANONYMOUS_APPROVAL,
        'basic_from_environment': settings.METRICS_BASIC_AUTH_USERS == json.loads(
            os.environ['METRICS_BASIC_AUTH_USERS'],
        ),
    }), flush=True)


if __name__ == '__main__':
    raise SystemExit(main(configure=configure, prepare=prepare))
