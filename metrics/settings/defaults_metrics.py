import json

from .defaults import *


def metrics_list_setting(name, default=None):
    raw_value = env.str(name, default=None)
    if raw_value is None:
        return default
    raw_text = raw_value.strip()
    if not raw_text:
        return []
    json_candidate = raw_text
    if len(raw_text) > 2 and raw_text[0] in {'"', "'"} and raw_text[-1] == raw_text[0]:
        quoted_inner = raw_text[1:-1].strip()
        if quoted_inner.startswith('['):
            json_candidate = quoted_inner
    if json_candidate.startswith('['):
        decoded_value = json.loads(json_candidate)
        if not isinstance(decoded_value, list):
            raise ValueError(f'{name} must be a list.')
        return metrics_normalize_list_items(decoded_value)
    return metrics_normalize_list_items(raw_text.split(','))


def metrics_normalize_list_items(values):
    normalized_values = []
    for value in values:
        text = str(value).strip()
        if len(text) >= 2 and text[0] in {'"', "'"} and text[-1] == text[0]:
            text = text[1:-1].strip()
        if text:
            normalized_values.append(text)
    return normalized_values


def metrics_absolute_state_path(raw_path):
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


METRICS_STATE_DIR = metrics_absolute_state_path(env.str('METRICS_STATE_DIR', default=str(BASE_DIR / 'state')))
METRICS_STATE_DIR.mkdir(parents=True, exist_ok=True)
METRICS_SQLITE_DATABASE_PATH = metrics_absolute_state_path(
    env.str('METRICS_SQLITE_DATABASE_PATH', default=str(METRICS_STATE_DIR / 'db.sqlite3'))
)
METRICS_TASK_SEARCH_CACHE_DIR = metrics_absolute_state_path(
    env.str('METRICS_TASK_SEARCH_CACHE_DIR', default=str(METRICS_STATE_DIR / 'task_search_cache'))
)

DATABASES['default']['NAME'] = METRICS_SQLITE_DATABASE_PATH

# Application deployment setup
METRICS_BASE_URL = env.str('METRICS_BASE_URL', default='')
METRICS_BASIC_AUTH_USERS = env.json('METRICS_BASIC_AUTH_USERS', default=None)

# Task tracker
METRICS_TASK_TRACKER = env.str('METRICS_TASK_TRACKER', default='jira')

METRICS_AZURE_ORGANIZATION_URL = env.str('METRICS_AZURE_ORGANIZATION_URL', default=None)
METRICS_AZURE_PAT = env.str('METRICS_AZURE_PAT', default=None)

METRICS_JIRA_SERVER_URL = env.str('METRICS_JIRA_SERVER_URL', default=None)
METRICS_JIRA_EMAIL = env.str('METRICS_JIRA_EMAIL', default=None)
METRICS_JIRA_API_TOKEN = env.str('METRICS_JIRA_API_TOKEN', default=None)
METRICS_JIRA_AUTH_MODE = env.str('METRICS_JIRA_AUTH_MODE', default='cloud_basic')
METRICS_JIRA_VERIFY_SSL = env.bool('METRICS_JIRA_VERIFY_SSL', default=True)
METRICS_JIRA_CA_BUNDLE = env.str('METRICS_JIRA_CA_BUNDLE', default=None)

# Pull request source (Bitbucket, used when the tracker is JIRA)
METRICS_BITBUCKET_URL = env.str('METRICS_BITBUCKET_URL', default='https://api.bitbucket.org/')
METRICS_BITBUCKET_WORKSPACE = env.str('METRICS_BITBUCKET_WORKSPACE', default=None)
METRICS_BITBUCKET_USERNAME = env.str('METRICS_BITBUCKET_USERNAME', default=None)
METRICS_BITBUCKET_APP_PASSWORD = env.str('METRICS_BITBUCKET_APP_PASSWORD', default=None)
METRICS_BITBUCKET_REPOSITORIES = metrics_list_setting('METRICS_BITBUCKET_REPOSITORIES', default=None)

# Pull request review gate configuration
METRICS_PR_MAIN_REVIEWER_LEVELS = metrics_list_setting('METRICS_PR_MAIN_REVIEWER_LEVELS', default=['lead', 'arch'])
METRICS_PR_MIN_DEVELOPER_APPROVALS = env.int('METRICS_PR_MIN_DEVELOPER_APPROVALS', default=2)

# Status codes

METRICS_IN_PROGRESS_STATUS_CODES = metrics_list_setting('METRICS_IN_PROGRESS_STATUS_CODES',
                                                        default=['Analysis', 'Active', 'In Progress',
                                                                 'In Development', 'QA', 'Validation',
                                                                 'Testing', 'Review'])
METRICS_PENDING_STATUS_CODES = metrics_list_setting('METRICS_PENDING_STATUS_CODES',
                                                    default=['Blocked', 'On Hold', 'Pending', 'Waiting'])
METRICS_DONE_STATUS_CODES = metrics_list_setting('METRICS_DONE_STATUS_CODES', default=['Done', 'Closed', 'Resolved'])

# Recently finished tasks configuration
METRICS_RECENTLY_FINISHED_TASKS_DAYS = env.int('METRICS_RECENTLY_FINISHED_TASKS_DAYS', default=14)

# Filters
METRICS_PROJECT_KEYS = metrics_list_setting('METRICS_PROJECT_KEYS', default=None)

METRICS_GLOBAL_TASK_TYPES_FILTER = metrics_list_setting('METRICS_GLOBAL_TASK_TYPES_FILTER', default=None)
METRICS_GLOBAL_TEAM_FILTER = metrics_list_setting('METRICS_GLOBAL_TEAM_FILTER', default=None)

# Calculations
METRICS_STORY_POINT_CUSTOM_FIELD_ID = env.str('METRICS_STORY_POINT_CUSTOM_FIELD_ID', default=None)

METRICS_JIRA_RELEASE_FIELD = env.str('METRICS_JIRA_RELEASE_FIELD', default='fixVersions')
METRICS_AZURE_RELEASE_FIELD = env.str('METRICS_AZURE_RELEASE_FIELD', default='System.IterationPath')

METRICS_JIRA_ITERATION_FIELD = env.str('METRICS_JIRA_ITERATION_FIELD', default='')
METRICS_AZURE_ITERATION_FIELD = env.str('METRICS_AZURE_ITERATION_FIELD', default='System.IterationPath')

METRICS_WORKING_DAYS_PER_MONTH = env.int('METRICS_WORKING_DAYS_PER_MONTH', default=22)
METRICS_IDEAL_HOURS_PER_DAY = env.float('METRICS_IDEAL_HOURS_PER_DAY', default=4.0)
METRICS_STORY_POINTS_TO_IDEAL_HOURS_CONVERTION_RATIO = env.float('METRICS_STORY_POINTS_TO_IDEAL_HOURS_CONVERTION_RATIO',
                                                                 default=1.0)

# Fallback values when missing
METRICS_DEFAULT_STORY_POINTS_VALUE_WHEN_MISSING = env.int('METRICS_DEFAULT_STORY_POINTS', default=None)
METRICS_DEFAULT_SENIORITY_LEVEL_WHEN_MISSING = env.str('METRICS_DEFAULT_SENIORITY_LEVEL_WHEN_MISSING', default='middle')
METRICS_DEFAULT_HEALTH_STATUS_WHEN_MISSING = env.str('METRICS_DEFAULT_HEALTH_STATUS_WHEN_MISSING', default='GREEN')

METRICS_MEMBER_GROUP_WHEN_MISSING = env.str('METRICS_MEMBER_GROUP_WHEN_MISSING', default=None)
METRICS_MERGE_UNASSIGNED_INTO_FILTERED_GROUP = env.bool('METRICS_MERGE_UNASSIGNED_INTO_FILTERED_GROUP', default=False)

METRICS_CURRENT_TASKS_LAZY_LOADING = env.bool('METRICS_CURRENT_TASKS_LAZY_LOADING', default=True)

METRICS_SCOPE_METADATA_CACHE_SECONDS = env.int('METRICS_SCOPE_METADATA_CACHE_SECONDS', default=300)
METRICS_PROVIDER_CACHE_ENABLED = env.bool('METRICS_PROVIDER_CACHE_ENABLED', default=True)
METRICS_PROVIDER_CACHE_TTL_SECONDS = env.int('METRICS_PROVIDER_CACHE_TTL_SECONDS', default=900)
METRICS_PROVIDER_METADATA_CACHE_SECONDS = env.int('METRICS_PROVIDER_METADATA_CACHE_SECONDS', default=300)
METRICS_PROVIDER_SYNC_STALE_AFTER_SECONDS = env.int('METRICS_PROVIDER_SYNC_STALE_AFTER_SECONDS', default=1800)
METRICS_PROVIDER_CACHE_OVERRIDES = env.json('METRICS_PROVIDER_CACHE_OVERRIDES', default={})

METRICS_HSDES_LIVE_SYNC_ENABLED = env.bool('METRICS_HSDES_LIVE_SYNC_ENABLED', default=False)
METRICS_HSDES_API_BASE_URL = env.str('METRICS_HSDES_API_BASE_URL', default='https://hsdes-api.intel.com/rest')
METRICS_HSDES_AUTH_MODE = env.str('METRICS_HSDES_AUTH_MODE', default='kerberos')
METRICS_HSDES_HTTP_TRANSPORT = env.str('METRICS_HSDES_HTTP_TRANSPORT', default='auto')
METRICS_HSDES_USERNAME = env.str('METRICS_HSDES_USERNAME', default='')
METRICS_HSDES_PASSWORD = env.str('METRICS_HSDES_PASSWORD', default='')
METRICS_HSDES_TOKEN = env.str('METRICS_HSDES_TOKEN', default='')
METRICS_HSDES_TIMEOUT_SECONDS = env.int('METRICS_HSDES_TIMEOUT_SECONDS', default=30)
METRICS_RUN_PROVIDER_PERF_TESTS = env.bool('METRICS_RUN_PROVIDER_PERF_TESTS', default=False)

METRICS_AI_SIDECAR_ENABLED = env.bool('METRICS_AI_SIDECAR_ENABLED', default=False)
METRICS_AI_BASE_URL = env.str('METRICS_AI_BASE_URL', default='http://127.0.0.1:48300')
METRICS_AI_BASE_FRONTEND_URL = env.str('METRICS_AI_BASE_FRONTEND_URL', default='')
METRICS_AI_BASE_SERVICE_ID = env.str('METRICS_AI_BASE_SERVICE_ID', default='dashboard-query-agent-app-service')
METRICS_AI_BASE_PROFILE_ID = env.str('METRICS_AI_BASE_PROFILE_ID', default='dashboard_query_agent')
METRICS_AI_BASE_INSTANCE_TOKEN = env.str('METRICS_AI_BASE_INSTANCE_TOKEN', default='')
METRICS_AI_BASE_HANDSHAKE_PATH = env.str('METRICS_AI_BASE_HANDSHAKE_PATH', default='/health/handshake')
METRICS_AI_BASE_TIMEOUT_SECONDS = env.int('METRICS_AI_BASE_TIMEOUT_SECONDS', default=3)
METRICS_AI_BASE_EMBED_MODE = env.str('METRICS_AI_BASE_EMBED_MODE', default='workbench')
METRICS_AI_GRAFANA_BASE_URL = env.str('METRICS_AI_GRAFANA_BASE_URL', default='http://127.0.0.1:3001')
METRICS_AI_GRAFANA_USERNAME = env.str('METRICS_AI_GRAFANA_USERNAME', default='admin')
METRICS_AI_GRAFANA_PASSWORD = env.str('METRICS_AI_GRAFANA_PASSWORD', default='admin')

METRICS_AVAILABLE_MEMBER_STAGES_FILTER = metrics_list_setting('METRICS_AVAILABLE_MEMBER_STAGES_FILTER', default=[])

METRICS_TASK_FILTER_FIELDS = metrics_list_setting('METRICS_TASK_FILTER_FIELDS',
                                                  default=['health', 'priority', 'release', 'iteration',
                                                           'assignee', 'parent'])

# Velocity time unit configuration
METRICS_DEFAULT_VELOCITY_TIME_UNIT = env.str('METRICS_DEFAULT_VELOCITY_TIME_UNIT', default='DAY')

CACHES['task_search_results'] = {
    'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
    'LOCATION': str(METRICS_TASK_SEARCH_CACHE_DIR),
    "OPTIONS": {"MAX_ENTRIES": 100000},
    'TIMEOUT': 300
}

METRICS_SENIORITY_LEVELS = env.dict('METRICS_SENIORITY_LEVELS', default={
    'arch': 1.0,
    'lead': 1.0,
    'senior': 1.0,
    'middle': 2.0,
    'junior': 4.0,
}, subcast=float)

METRICS_STAGES = env.json('METRICS_STAGES', default={
    'Analysis': ['Analysis'],
    'Development': ['Active', 'In Progress', 'In Development', 'Review'],
    'Validation': ['QA', 'Validation', 'Testing'],
    'Recently Finished': ['Done', 'Closed', 'Resolved'],
    'Pending': ['Blocked', 'On Hold', 'Pending', 'Waiting'],
})

METRICS_STAGE_SORT_OVERRIDES = env.json('METRICS_STAGE_SORT_OVERRIDES', default={})

METRICS_DEFAULT_SORT_CRITERIA = env.str('METRICS_DEFAULT_SORT_CRITERIA', default='-health,-spent_time')

METRICS_MEMBERS = env.json('METRICS_MEMBERS', default={})

METRICS_MEMBER_GROUP_CUSTOM_FILTERS = env.json('METRICS_MEMBER_GROUP_CUSTOM_FILTERS', default={})
