from __future__ import annotations

import json
import os
from pathlib import Path
import re
from unittest.mock import patch

from scripts.validation.project_full_stack_support import require_owned_run_dir


RUN_DIR = require_owned_run_dir(os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'])
BOOTSTRAP = os.environ.get('METRICS_PROJECT_FULL_STACK_BOOTSTRAP') == '1'
STATE_DIR = RUN_DIR / 'environment' / 'state'
DB_PATH = RUN_DIR / 'catalog.sqlite3'
ARCHIVE_ROOT = RUN_DIR / 'archive'

os.environ['METRICS_STATE_DIR'] = str(STATE_DIR)
os.environ['METRICS_SQLITE_DATABASE_PATH'] = str(DB_PATH)
os.environ['METRICS_TASK_SEARCH_CACHE_DIR'] = str(RUN_DIR / 'environment' / 'task-cache')
os.environ['METRICS_PROJECT_ARCHIVE_ROOT'] = str(ARCHIVE_ROOT)
os.environ['METRICS_PROJECT_ARCHIVE_AUTHOR_NAME'] = 'Synthetic Validation'
os.environ['METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL'] = 'validation@example.test'
os.environ['METRICS_BASIC_AUTH_USERS'] = json.dumps({
    'SYNTHETIC_ALICE': 'SYNTHETIC_ALICE_PASSWORD',
    'SYNTHETIC_BOB': 'SYNTHETIC_BOB_PASSWORD',
})
os.environ['METRICS_JIRA_SERVER_URL'] = 'https://tracker.example.test/jira'
os.environ['METRICS_JIRA_AUTH_MODE'] = 'server_pat'
os.environ['METRICS_JIRA_EMAIL'] = ''
os.environ['METRICS_JIRA_API_TOKEN'] = ''
os.environ['METRICS_HSDES_USERNAME'] = ''
os.environ['METRICS_HSDES_PASSWORD'] = ''
os.environ['METRICS_HSDES_TOKEN'] = ''
os.environ['SECRET_KEY'] = 'django-insecure-synthetic-full-stack-qualification'

with patch('environs.Env.read_env', lambda self, *args, **kwargs: None):
    from metrics.settings.defaults_metrics import *  # noqa: F401,F403,E402

INSTALLED_APPS = INSTALLED_APPS + ('scripts.validation.project_ui_fixture_app.ProjectUiFixtureAppConfig',)
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
DATABASES['default']['NAME'] = DB_PATH
METRICS_SQLITE_DATABASE_PATH = DB_PATH
METRICS_STATE_DIR = STATE_DIR
METRICS_TASK_SEARCH_CACHE_DIR = RUN_DIR / 'environment' / 'task-cache'
METRICS_PROJECT_ARCHIVE_ROOT = str(ARCHIVE_ROOT)
METRICS_PROJECT_RUN_ENABLED = True
METRICS_PROJECT_RUN_TIMEOUT_SECONDS = 600
METRICS_PROJECT_RUN_MAX_ANALYSIS_ITEMS = 10
METRICS_PROJECT_RUN_MAX_OBSERVATIONS_PER_ATTEMPT = 16
METRICS_PROJECT_RUN_MAX_QUEUED = 16
METRICS_PROJECT_CAPTURE_PAGE_SIZE = 2
METRICS_BASIC_AUTH_USERS = {'SYNTHETIC_ALICE': 'SYNTHETIC_ALICE_PASSWORD', 'SYNTHETIC_BOB': 'SYNTHETIC_BOB_PASSWORD'}
METRICS_PROJECT_LOCAL_OPERATOR_USERNAME = ''
METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE = [{
    'profile_id': 'synthetic-jira',
    'provider_id': 'jira',
    'display_name': 'Qualification Jira',
    'enabled': True,
    'connection_settings': {
        'base_url': 'https://tracker.example.test/jira',
        'auth_mode': 'server_pat',
        'credentials': {'token': 'synthetic-only-token'},
        'verify_ssl': True,
    },
    'source_population': {'native_query_text': 'project = ALPHA AND issuekey = ALPHA-101'},
}]

_cookie_base = re.sub(r'[^A-Za-z0-9_]', '_', RUN_DIR.name)
SESSION_COOKIE_NAME = f'w7_{_cookie_base}_sessionid'
CSRF_COOKIE_NAME = f'w7_{_cookie_base}_csrftoken'
LANGUAGE_COOKIE_NAME = f'w7_{_cookie_base}_language'


def METRICS_PROJECT_RUNTIME_FACTORY():
    from scripts.validation.project_full_stack_fixture import build_runtime_environment

    connection = json.loads((RUN_DIR / 'base' / 'connection.json').read_text(encoding='utf-8'))
    return build_runtime_environment(connection)


if BOOTSTRAP:
    Path(METRICS_TASK_SEARCH_CACHE_DIR).mkdir(parents=True, exist_ok=True)
