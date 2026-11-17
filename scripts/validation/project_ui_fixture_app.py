from django.apps import AppConfig
from django.conf import settings
from datetime import UTC, datetime
import json
import sys


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


class ProjectRunFixtureAppConfig(ProjectUiFixtureAppConfig):
    label = 'project_run_fixture_app'

    def ready(self):
        super().ready()
        if not getattr(settings, 'RUN_DIR', None):
            raise ValueError('A controlled full-stack run directory is required.')
        self._install_provider_access_fixture()
        if settings.METRICS_PROJECT_VALIDATION_SCENARIO == 'full-week':
            self._install_reference_fixture()

    def _install_reference_fixture(self):
        from provider_sync.app.api import references

        transcript = settings.RUN_DIR / 'evidence/reference-requests.jsonl'

        def create_synthetic_reference_reader(settings_source=None, *, reader=None, resolver=None):
            return reader if reader is not None else WeekReferenceReader(transcript)

        references.create_provider_reference_reader = create_synthetic_reference_reader
        report_factories = sys.modules.get('project_management.app.api.report_factories')
        if report_factories is not None:
            report_factories.create_provider_reference_reader = create_synthetic_reference_reader

    def _install_provider_access_fixture(self):
        from provider_sync.app.api import access_factory
        from project_management.app.api.factories import build_capture_archive_service, build_project_api

        def create_synthetic_provider_access_service():
            project_api = build_project_api()
            archive = build_capture_archive_service(project_api=project_api)
            provider_factory = self._provider_factory()
            return provider_factory(project_api, archive).service

        access_factory.create_provider_access_service = create_synthetic_provider_access_service
        run_factories = sys.modules.get('project_management.app.api.run_factories')
        if run_factories is not None:
            run_factories.create_provider_access_service = create_synthetic_provider_access_service

    def _provider_factory(self):
        scenario = settings.METRICS_PROJECT_VALIDATION_SCENARIO
        if scenario == 'full-week':
            from scripts.validation.project_week_fixture import create_week_provider

            run_dir = settings.RUN_DIR
            return lambda project_api, archive: create_week_provider(project_api, archive, run_dir)
        if scenario != 'single':
            raise ValueError('Unsupported validation scenario.')
        from scripts.validation.project_full_stack_fixture import create_provider_fixture

        return create_provider_fixture


class WeekReferenceReader:
    def __init__(self, transcript):
        self.path = transcript

    def supports(self, stage, principal_id):
        from scripts.validation.project_week_data import WEEK_QUERY

        return stage.descriptor.query == WEEK_QUERY and principal_id == 'principal-1'

    def read(self, context, member):
        from project_management.app.domain.report_completion import ReferenceObservation
        from scripts.validation.project_full_stack_fixture import ENDPOINT
        from scripts.validation.project_week_fixture import week_issues

        row = next((item for item in week_issues() if item['id'] == member.stable_id), None)
        if row is None:
            raise AssertionError('Reference is not in the fixed qualification population.')
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stable_id': member.stable_id, 'scope_hash': context['membership_proof_hash']}) + '\n')
        return ReferenceObservation(
            identity={'provider_id': member.provider_id, 'endpoint_id': member.endpoint_id,
                      'stable_id': member.stable_id, 'display_key': member.display_key},
            requested_key=member.display_key, current_key=member.display_key,
            canonical_url=f'{ENDPOINT}/browse/{row["key"]}', title=row['fields']['summary'],
            assignee={'id': row['fields']['assignee']['key'], 'display_name': row['fields']['assignee']['displayName']},
            assignee_state='assigned', observed_at=datetime.now(UTC).isoformat(),
            source_updated_at='2026-11-01T01:00:00+00:00', lookup_kind='live',
            scope_snapshot_hash=context['membership_proof_hash'],
        )
