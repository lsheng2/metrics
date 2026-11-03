import os

from provider_sync.tests.connection_test_settings import *


DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ["PROVIDER_CREDENTIALS_PROCESS_DB"]}}
METRICS_PROVIDER_SECRET_DIR = os.environ["PROVIDER_CREDENTIALS_PROCESS_SECRET_DIR"]
