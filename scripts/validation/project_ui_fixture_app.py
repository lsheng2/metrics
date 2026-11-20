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
        self._install_scope_metadata_fixture()

    def _install_scope_metadata_fixture(self):
        from jira_sync import container as jira_container_module
        from jira_sync.app.api.scope_metadata import ApiForScopeMetadata
        from ui_web import container as ui_container_module

        class SyntheticJiraSyncContainer:
            @property
            def jira_sync_api(self):
                return jira_container_module.jira_sync_api

            @property
            def scope_metadata_api(self):
                return ApiForScopeMetadata({'jira': SyntheticScopeMetadataProvider()}, cache_timeout_seconds=0)

        synthetic_container = SyntheticJiraSyncContainer()
        jira_container_module.jira_sync_container = synthetic_container
        ui_container_module.jira_sync_container = synthetic_container
        ui_container_module.ui_web_container._bug_trend_facade = None


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


class SyntheticScopeMetadataProvider:
    def discover_options(self, query: str, selected_projects: list[str], selected_item_types: list[str]):
        from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption

        if 'ERR' in query or 'ERR' in selected_projects:
            raise RuntimeError('Synthetic metadata unavailable')
        project = 'ALT' if 'ALT' in query or 'ALT' in selected_projects else 'SYNTH'
        if project == 'ALT':
            return ScopeConfigOptions(
                projects=[TrackerOption('ALT', 'ALT')],
                item_types=[TrackerOption('bug-alt', 'Regression Bug')],
                statuses=[TrackerOption('triaged', 'Triaged'), TrackerOption('resolved', 'Resolved')],
                resolutions=[TrackerOption('verified', 'Verified')],
                priorities=[TrackerOption('p0', 'P0-Blocker')],
                fields=[TrackerFieldOption('customfield_alt_severity', 'Synthetic severity', 'Synthetic severity (customfield_alt_severity)')],
                components=[TrackerOption('platform', 'Platform')],
                versions=[TrackerOption('2026.alt', '2026.alt')],
            )
        return ScopeConfigOptions(
            projects=[TrackerOption('SYNTH', 'SYNTH')],
            item_types=[TrackerOption('bug', 'Bug')],
            statuses=[TrackerOption('open', 'Open'), TrackerOption('fixed', 'Fixed'), TrackerOption('closed', 'Closed')],
            resolutions=[TrackerOption('done', 'Done')],
            priorities=[TrackerOption('p1', 'P1-Synthetic')],
            fields=[TrackerFieldOption('priority', 'Priority', 'Priority')],
            components=[TrackerOption('ui', 'UI')],
            versions=[TrackerOption('2026.01', '2026.01')],
        )

    def discover_field_values(self, project_id: str, item_type_ids: list[str], field_id: str):
        from jira_sync.app.api.scope_metadata import TrackerOption

        return [TrackerOption('synthetic-value', 'Synthetic value')]


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
