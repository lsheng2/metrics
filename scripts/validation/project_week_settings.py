from copy import deepcopy

from scripts.validation.project_full_stack_settings import *  # noqa: F401,F403
METRICS_PROJECT_VALIDATION_SCENARIO = 'full-week'
from scripts.validation.project_week_data import WEEK_QUERY


METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE = deepcopy(METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE)
METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE[0]['source_population']['native_query_text'] = WEEK_QUERY
