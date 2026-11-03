import os

from provider_sync.tests.connection_test_settings import *


DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ['PROVIDER_ACCESS_TEST_DB']}}
METRICS_PROJECT_ARCHIVE_ROOT = ''
