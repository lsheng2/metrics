"""Explicit-only consumer lane; the SDK plugin injects the applicable assertions."""
import pytest


def test_asgi_not_declared():
    pytest.skip('not applicable: host did not declare asgi')
