import os

from metrics.settings.development import *


DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ['PM_TEST_DATABASE']}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
