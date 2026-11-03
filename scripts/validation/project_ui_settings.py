import json
import os
import hashlib
import re
from pathlib import Path
from unittest.mock import patch

from scripts.validation.project_ui_fixture_guard import validate_settings_startup


_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_ROOT = validate_settings_startup(
    allow_bootstrap=os.environ.get('METRICS_PROJECT_UI_FIXTURE_BOOTSTRAP') == '1',
)
_STATE_DIR = _FIXTURE_ROOT / 'runtime-state'
_DB_PATH = _FIXTURE_ROOT / 'project-ui.sqlite3'

os.environ['METRICS_STATE_DIR'] = str(_STATE_DIR)
os.environ['METRICS_SQLITE_DATABASE_PATH'] = str(_DB_PATH)
os.environ['METRICS_BASIC_AUTH_USERS'] = json.dumps({
    'SYNTHETIC_ALICE': 'SYNTHETIC_ALICE_PASSWORD',
    'SYNTHETIC_BOB': 'SYNTHETIC_BOB_PASSWORD',
})
os.environ['METRICS_JIRA_SERVER_URL'] = 'https://synthetic-jira.example.test'
os.environ['METRICS_HSDES_API_BASE_URL'] = 'https://synthetic-hsdes.example.test/rest'
os.environ['METRICS_HSDES_USERNAME'] = ''
os.environ['METRICS_HSDES_PASSWORD'] = ''
os.environ['METRICS_HSDES_TOKEN'] = ''
os.environ['METRICS_JIRA_EMAIL'] = ''
os.environ['METRICS_JIRA_API_TOKEN'] = ''
os.environ['SECRET_KEY'] = 'django-insecure-synthetic-project-ui-validation'

with patch('environs.Env.read_env', lambda self, *args, **kwargs: None), \
        patch('pathlib.Path.mkdir', lambda self, *args, **kwargs: None):
    from metrics.settings.defaults_metrics import *  # noqa: F401,F403,E402

INSTALLED_APPS = INSTALLED_APPS + ('scripts.validation.project_ui_fixture_app.ProjectUiFixtureAppConfig',)


DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
DATABASES['default']['NAME'] = _DB_PATH
METRICS_SQLITE_DATABASE_PATH = _DB_PATH
METRICS_STATE_DIR = _STATE_DIR
METRICS_TASK_SEARCH_CACHE_DIR = _STATE_DIR / 'task_search_cache'
METRICS_BASIC_AUTH_USERS = {
    'SYNTHETIC_ALICE': 'SYNTHETIC_ALICE_PASSWORD',
    'SYNTHETIC_BOB': 'SYNTHETIC_BOB_PASSWORD',
}
METRICS_PROJECT_LOCAL_OPERATOR_USERNAME = ''
METRICS_JIRA_SERVER_URL = 'https://synthetic-jira.example.test'
METRICS_HSDES_API_BASE_URL = 'https://synthetic-hsdes.example.test/rest'

_COOKIE_BASENAME = re.sub(r'[^a-zA-Z0-9_]', '_', _FIXTURE_ROOT.name)[:32]
_COOKIE_HASH = hashlib.sha256(str(_FIXTURE_ROOT.resolve()).encode('utf-8')).hexdigest()[:12]
_COOKIE_PREFIX = f'w2_{_COOKIE_BASENAME}_{_COOKIE_HASH}'
SESSION_COOKIE_NAME = f'{_COOKIE_PREFIX}_sessionid'
CSRF_COOKIE_NAME = f'{_COOKIE_PREFIX}_csrftoken'
LANGUAGE_COOKIE_NAME = f'{_COOKIE_PREFIX}_language'

METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE = [
    {
        'profile_id': 'synthetic-jira',
        'provider_id': 'jira',
        'display_name': 'Synthetic Jira',
        'enabled': True,
        'connection_settings': {
            'base_url': 'https://synthetic-jira.example.test',
            'api_token': 'SYNTHETIC_ONLY_NOT_REAL',
        },
        'source_population': {'native_query_text': 'project = SYNTH'},
    },
    {
        'profile_id': 'synthetic-hsd',
        'provider_id': 'hsdes',
        'display_name': 'Synthetic HSD',
        'enabled': True,
        'connection_settings': {
            'base_url': 'https://synthetic-hsdes.example.test/rest',
            'token': 'SYNTHETIC_ONLY_NOT_REAL',
        },
        'source_population': {
            'source_query_ref': 'synthetic-saved-query',
            'source_query_hash': 'synthetic-hsd-version',
            'criteria_snapshot': '{"project":"SYNTH"}',
            'exclusion_snapshot': '[]',
            'tenant_or_site': 'synthetic.intel.example',
            'subject_or_issue_type': 'bug',
        },
    },
]
