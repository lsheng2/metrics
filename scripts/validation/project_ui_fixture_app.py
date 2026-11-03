from django.apps import AppConfig
from django.conf import settings


class ProjectUiFixtureAppConfig(AppConfig):
    name = 'scripts.validation.project_ui_fixture_app'
    label = 'project_ui_fixture_app'
    path = str(settings.BASE_DIR / 'scripts' / 'validation')

    def ready(self):
        records = getattr(settings, 'METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE', None)
        if records is None:
            return

        from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry

        def load_synthetic_default(cls):
            return cls.from_records(records)

        ProjectProviderProfileRegistry.load_default = classmethod(load_synthetic_default)
