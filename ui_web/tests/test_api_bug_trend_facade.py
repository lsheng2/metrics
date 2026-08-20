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
    scope_id: int
    calculation_run_id: str
    labels: list
    bucket_ids: list
    datasets: list
    unavailable_reason: str = ''
    run_metadata: FakeRunMetadata = None


class FakeBugTrendApi:
    def list_enabled_scopes(self):
        return [FakeScope(7, 'STDEL emulation', 'NVU', 'STDEL')]

    def get_chart(self, scope_id, begin, end):
        return FakeChart(
            scope_id=scope_id,
            calculation_run_id='run-123',
            labels=['26WW32'],
            bucket_ids=['bucket-123'],
            datasets=[FakeDataset('all_open_bugs', 'line', [8], '#f2c94c')],
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


class TestBugTrendFacade(TestCase):
    def test_shouldExposeSavedScopeOptions(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        options = facade.get_scope_options()

        # Then
        self.assertEqual('NVU / STDEL / STDEL emulation', options[0].label)

    def test_shouldReturnChartJsonWithRunAndBucketIds(self):
        # Given
        facade = BugTrendFacade(FakeBugTrendApi())

        # When
        chart = facade.get_chart_data(7, None, None)
        chart_json = facade.get_chart_json(chart)

        # Then
        self.assertIn('run-123', chart_json)
        self.assertIn('bucket-123', chart_json)
        self.assertIn('all_open_bugs', chart_json)
        self.assertIn('fresh', chart_json)