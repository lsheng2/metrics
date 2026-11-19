import importlib

from django.test import override_settings


@override_settings(METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE=[])
def test_ui_profile_fixture_does_not_replace_provider_access(monkeypatch):
    from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
    from provider_sync.app.api import access_factory
    from scripts.validation.project_ui_fixture_app import ProjectUiFixtureAppConfig

    original = ProjectProviderProfileRegistry.__dict__['load_default']
    monkeypatch.setattr(ProjectProviderProfileRegistry, 'load_default', original)
    marker = lambda: object()
    monkeypatch.setattr(access_factory, 'create_provider_access_service', marker)
    module = importlib.import_module('scripts.validation.project_ui_fixture_app')
    ProjectUiFixtureAppConfig(module.__name__, module).ready()
    assert access_factory.create_provider_access_service is marker
