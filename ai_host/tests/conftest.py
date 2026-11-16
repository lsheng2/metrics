import pytest


@pytest.fixture(scope='session')
def django_db_modify_db_settings(tmp_path_factory):
    from django.conf import settings

    # Runtime callbacks own worker-thread connections; in-memory Django databases
    # deliberately ignore close(), unlike the deployed file-backed SQLite store.
    settings.DATABASES['default'].setdefault('TEST', {})['NAME'] = str(
        tmp_path_factory.mktemp('ai-host-db') / 'catalog.sqlite3',
    )
