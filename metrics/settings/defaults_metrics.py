from .defaults import *


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
METRICS_BITBUCKET_REPOSITORIES = env.list('METRICS_BITBUCKET_REPOSITORIES', default=None)

# Pull request review gate configuration
METRICS_PR_MAIN_REVIEWER_LEVELS = env.list('METRICS_PR_MAIN_REVIEWER_LEVELS', default=['lead', 'arch'])
METRICS_PR_MIN_DEVELOPER_APPROVALS = env.int('METRICS_PR_MIN_DEVELOPER_APPROVALS', default=2)

# Status codes

METRICS_IN_PROGRESS_STATUS_CODES = env.list('METRICS_IN_PROGRESS_STATUS_CODES',
                                            default=['Analysis', 'Active', 'In Progress', 'In Development', 'QA',
                                                     'Validation', 'Testing', 'Review'])
METRICS_PENDING_STATUS_CODES = env.list('METRICS_PENDING_STATUS_CODES',
                                        default=['Blocked', 'On Hold', 'Pending', 'Waiting'])
METRICS_DONE_STATUS_CODES = env.list('METRICS_DONE_STATUS_CODES', default=['Done', 'Closed', 'Resolved'])

# Recently finished tasks configuration
METRICS_RECENTLY_FINISHED_TASKS_DAYS = env.int('METRICS_RECENTLY_FINISHED_TASKS_DAYS', default=14)

# Filters
METRICS_PROJECT_KEYS = env.list('METRICS_PROJECT_KEYS', default=None)

METRICS_GLOBAL_TASK_TYPES_FILTER = env.list('METRICS_GLOBAL_TASK_TYPES_FILTER', default=None)
METRICS_GLOBAL_TEAM_FILTER = env.list('METRICS_GLOBAL_TEAM_FILTER', default=None)

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

METRICS_AVAILABLE_MEMBER_STAGES_FILTER = env.list('METRICS_AVAILABLE_MEMBER_STAGES_FILTER', default=[])

METRICS_TASK_FILTER_FIELDS = env.list('METRICS_TASK_FILTER_FIELDS',
                                      default=['health', 'priority', 'release', 'iteration', 'assignee', 'parent'])

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
