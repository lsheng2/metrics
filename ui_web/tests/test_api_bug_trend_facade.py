from dataclasses import dataclass
from unittest import TestCase

from ui_web.facades.bug_trend_facade import BugTrendFacade


@dataclass(slots=True)
class FakeScope:
    id: int
    name: str
    ip: str
    project_label: str


@dataclass(slots=True)
class FakeDataset:
    series_name: str
    chart_type: str
    values: list
    color: str


@dataclass(slots=True)
class FakeRunMetadata:
    calculation_run_id: str
    run_config_version_hash: str
    current_config_version_hash: str
    freshness_status: str
    source_coverage_start: str
    source_coverage_end: str
    completed_at: str


@dataclass(slots=True)
class FakeChart:
    chart_id: str
    scope_id: int
    contract_version: str
    calculation_run_id: str
    labels: list
    bucket_ids: list
    datasets: list
    unavailable_reason: str = ''
    run_metadata: FakeRunMetadata = None
    current_evidence_available: bool = True
    bucket_starts: list = None
    bucket_ends: list = None
    bucket_granularity: str = 'weekly'


class FakeBugTrendApi:
    def __init__(self):
        self.saved_configs = []

    def list_enabled_scopes(self):
        return [FakeScope(7, 'STDEL emulation', 'NVU', 'STDEL')]

    def list_scope_configs(self):
        return [FakeScope(7, 'STDEL emulation', 'NVU', 'STDEL')]

    def get_chart(self, scope_id, begin, end, chart_id='default_bug_trend'):
        return FakeChart(
            chart_id=chart_id,
            scope_id=scope_id,
            contract_version='0.1',
            calculation_run_id='run-123',
            labels=['26WW32'],
            bucket_ids=['bucket-123'],
            datasets=[FakeDataset('all_open_bugs', 'line', [8], '#f2c94c')],
            bucket_starts=['2026-08-03'],
            bucket_ends=['2026-08-09'],
            run_metadata=FakeRunMetadata(
                'run-123',
                'run-hash',
                'current-hash',
                'fresh',
                '2026-08-03',
                '2026-08-09',
                '2026-08-19T00:00:00+00:00',
            ),
        )

    def get_scope_config(self, scope_id):
        return self._scope_config(scope_id, enabled=True)

    def save_scope_config(self, config):
        config.id = config.id or 42
        config.config_version_hash = 'new-hash'
        self.saved_configs.append(config)
        return config

    def disable_scope_config(self, scope_id):
        return self._scope_config(scope_id, enabled=False)

    def _scope_config(self, scope_id, enabled):
        from bug_metrics.app.api.scope_config import SavedScopeConfig
        return SavedScopeConfig(
            id=scope_id,
            name='STDEL emulation',
            ip='NVU',
            project_label='STDEL',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            terminal_excluded_status_values=[],
            fixed_resolution_values=[],
            closed_resolution_values=[],
            reopen_status_values=[],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            team_field='',
            milestone_field='',
            fix_version_field='fixVersions',
            package_version_field='',
            display_fields=[],
            timezone='UTC',
            bucket_granularity='weekly',
            enabled=enabled,
            config_version_hash='old-hash',
        )


class FailingScopeMetadataApi:
    def discover_scope_options(self, *args, **kwargs):
        raise RuntimeError('metadata discovery must not run')

    def discover_field_values(self, *args, **kwargs):
        raise RuntimeError('metadata discovery must not run')


class TestBugTrendFacade(TestCase):
    def test_shouldExposeSavedScopeOptions(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        options = facade.get_scope_options()

        # Then
        self.assertEqual('NVU / STDEL / STDEL emulation', options[0].label)

    def test_shouldExposeAllScopeConfigsForLibrary(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        scopes = facade.get_scope_library()

        # Then
        self.assertEqual('STDEL emulation', scopes[0].name)

    def test_shouldCreateDraftScopeWithoutExistingId(self):
        # Given
        bug_trend_api = FakeBugTrendApi()
        facade = BugTrendFacade(bug_trend_api)

        # When
        saved, hash_changed = facade.save_scope_config({
            'id': '',
            'name': 'STDEL new',
            'ip': 'NVU',
            'project_label': 'STDEL',
            'jql': 'project = STDEL AND issuetype = Bug',
            'bug_type_values': 'Bug',
            'bucket_granularity': 'weekly',
            'action': 'save_draft',
        })

        # Then
        self.assertEqual(42, saved.id)
        self.assertFalse(saved.enabled)
        self.assertTrue(hash_changed)

    def test_shouldCreateEnabledScopeWhenOperatorChoosesSaveAndEnable(self):
        # Given
        bug_trend_api = FakeBugTrendApi()
        facade = BugTrendFacade(bug_trend_api)

        # When
        saved, _ = facade.save_scope_config({
            'id': '',
            'name': 'STDEL enabled',
            'ip': 'NVU',
            'project_label': 'STDEL',
            'jql': 'project = STDEL AND issuetype = Bug',
            'bug_type_values': 'Bug',
            'bucket_granularity': 'weekly',
            'action': 'save_enable',
        })

        # Then
        self.assertTrue(saved.enabled)

    def test_shouldSaveDraftWithoutDisablingExistingEnabledScope(self):
        # Given
        bug_trend_api = FakeBugTrendApi()
        facade = BugTrendFacade(bug_trend_api)

        # When
        saved, _ = facade.save_scope_config({
            'id': '7',
            'name': 'STDEL emulation',
            'ip': 'NVU',
            'project_label': 'STDEL',
            'jql': 'project = STDEL AND issuetype = Bug',
            'bug_type_values': 'Bug',
            'bucket_granularity': 'weekly',
            'enabled': 'on',
            'action': 'save_draft',
        })

        # Then
        self.assertTrue(saved.enabled)

    def test_shouldPreserveExistingEnabledStateWhenCheckboxIsMissing(self):
        # Given
        bug_trend_api = FakeBugTrendApi()
        facade = BugTrendFacade(bug_trend_api)

        # When
        saved, _ = facade.save_scope_config({
            'id': '7',
            'name': 'STDEL emulation',
            'ip': 'NVU',
            'project_label': 'STDEL',
            'jql': 'project = STDEL AND issuetype = Bug',
            'bug_type_values': 'Bug',
            'bucket_granularity': 'weekly',
            'action': 'save_draft',
        })

        # Then
        self.assertTrue(saved.enabled)

    def test_shouldDuplicateScopeAsDisabledDraft(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        duplicate = facade.duplicate_scope_config(7)

        # Then
        self.assertIsNone(duplicate.id)
        self.assertEqual('STDEL emulation copy', duplicate.name)
        self.assertFalse(duplicate.enabled)
        self.assertEqual(['Bug'], duplicate.bug_type_values)

    def test_shouldReturnChartJsonWithRunAndBucketIds(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        chart = facade.get_chart_data(7, None, None)
        chart_json = facade.get_chart_json(chart)

        # Then
        self.assertIn('run-123', chart_json)
        self.assertIn('default_bug_trend', chart_json)
        self.assertIn('0.1', chart_json)
        self.assertIn('bucket-123', chart_json)
        self.assertIn('all_open_bugs', chart_json)
        self.assertIn('fresh', chart_json)
        self.assertIn('grafana_rows', chart_json)
        self.assertIn('bucket_label', chart_json)

    def test_shouldNotUseMetadataDiscoveryForRuntimeChartData(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi(), FailingScopeMetadataApi())

        # When
        chart = facade.get_chart_data(7, None, None)

        # Then
        self.assertEqual('run-123', chart.calculation_run_id)

    def test_shouldExposeChartContractVersionInPayload(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        chart = facade.get_chart_data(7, None, None)
        payload = facade.get_chart_payload(chart)

        # Then
        self.assertEqual('0.1', payload['contract_version'])