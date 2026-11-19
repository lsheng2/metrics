from importlib.util import find_spec

from django.conf import settings
import pytest


@pytest.mark.parametrize("module", ["metrics.wsgi", "metrics.asgi"])
def test_standalone_wsgi_and_asgi_entrypoints_are_not_exposed(module):
    assert find_spec(module) is None


def test_settings_do_not_override_framework_wsgi_application():
    assert not settings.is_overridden("WSGI_APPLICATION")
