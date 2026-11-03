import os
from pathlib import Path

from environs import Env


def _ignore_dotenv(self, *args, **kwargs):
    return None


Env.read_env = _ignore_dotenv

_ROOT = Path(__file__).resolve().parents[2] / ".tmp" / "provider-connection-tests"
os.environ["METRICS_STATE_DIR"] = str(_ROOT / "state")
os.environ["METRICS_SQLITE_DATABASE_PATH"] = str(_ROOT / "db.sqlite3")
os.environ["METRICS_TASK_SEARCH_CACHE_DIR"] = str(_ROOT / "task-cache")
os.environ["METRICS_JIRA_SERVER_URL"] = "https://jira.settings.example/jira"
os.environ["METRICS_JIRA_EMAIL"] = "settings-user@example.com"
os.environ["METRICS_JIRA_API_TOKEN"] = "settings-jira-token"
os.environ["METRICS_JIRA_AUTH_MODE"] = "server_pat"
os.environ["METRICS_JIRA_VERIFY_SSL"] = "true"
os.environ["METRICS_JIRA_CA_BUNDLE"] = ""
os.environ["METRICS_HSDES_API_BASE_URL"] = "https://hsdes.settings.example/rest"
os.environ["METRICS_HSDES_AUTH_MODE"] = "kerberos"
os.environ["METRICS_HSDES_HTTP_TRANSPORT"] = "auto"
os.environ["METRICS_HSDES_USERNAME"] = ""
os.environ["METRICS_HSDES_PASSWORD"] = ""
os.environ["METRICS_HSDES_TOKEN"] = ""
os.environ["METRICS_PROVIDER_SECRET_DIR"] = str(_ROOT / "provider-secrets")
os.environ["METRICS_PROVIDER_SECRET_MAX_BYTES"] = "65536"

from metrics.settings.defaults_metrics import *

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(_ROOT / "db.sqlite3")}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
