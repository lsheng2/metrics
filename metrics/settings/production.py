from .defaults_metrics import *

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

COMPRESS_ENABLED = True

PRODUCTION_APPS = (
)
INSTALLED_APPS += PRODUCTION_APPS

METRICS_PRODUCTION_TASK_SEARCH_CACHE_DIR = metrics_absolute_state_path(
    env.str('METRICS_TASK_SEARCH_CACHE_DIR', default=str(METRICS_STATE_DIR / 'task_search_cache_prod'))
)

CACHES['task_search_results'] = {
    'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
    'LOCATION': str(METRICS_PRODUCTION_TASK_SEARCH_CACHE_DIR),
    "OPTIONS": {"MAX_ENTRIES": 100000},
    'TIMEOUT': 900
}
