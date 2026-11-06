from copy import deepcopy
import json

from scripts.validation.project_full_stack_settings import *  # noqa: F401,F403
from scripts.validation.project_week_data import WEEK_QUERY


METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE = deepcopy(METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE)
METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE[0]['source_population']['native_query_text'] = WEEK_QUERY


def METRICS_PROJECT_RUNTIME_FACTORY():
    from scripts.validation.project_week_fixture import build_week_runtime

    connection = json.loads((RUN_DIR / 'base' / 'connection.json').read_text(encoding='utf-8'))
    return build_week_runtime(connection, RUN_DIR)
