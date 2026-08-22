import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / 'scripts' / 'validate_grafana_artifacts.py'
ALLOWLIST_PATH = REPO_ROOT / 'docs' / 'grafana-approved-data-surfaces.json'

spec = spec_from_file_location('validate_grafana_artifacts', VALIDATOR_PATH)
validate_grafana_artifacts = module_from_spec(spec)
sys.modules[spec.name] = validate_grafana_artifacts
spec.loader.exec_module(validate_grafana_artifacts)


class TestGrafanaDataSurfaceContract(TestCase):
    def test_shouldAcceptCommittedBugTrendGrafanaArtifact(self):
        # Given
        artifact_root = REPO_ROOT / 'ops' / 'grafana'

        # When
        findings = validate_grafana_artifacts.validate_artifact_root(
            artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
        )

        # Then
        self.assertEqual([], findings)

    def test_shouldAcceptGrafanaArtifactUsingApprovedMetricsApi(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                self._evidence_link_artifact(),
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertEqual([], findings)

    def test_shouldRejectChartDataRenderTargetWithoutMetricsContract(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'metrics-bug-trend-api'},
                            'targets': [
                                {
                                    'url': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end&chart_id=default_bug_trend',
                                    'root_selector': '$.points',
                                    'columns': [
                                        {'selector': 'label', 'text': 'label'},
                                        {'selector': 'value', 'text': 'value'},
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('must declare metricsContract' in finding.message for finding in findings))

    def test_shouldAcceptGrafanaEvidenceArtifactUsingApprovedMetricsApiWithSelectionParams(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'metrics-bug-trend-api'},
                            'targets': [
                                {
                                    'path': '/api/charts/evidence/?scope_id=$scope&begin=$begin&end=$end&run=$run&bucket=$bucket&series=$series&chart_id=default_bug_trend'
                                }
                            ],
                        }
                    ]
                },
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertEqual([], findings)

    def test_shouldAcceptGrafanaArtifactWhenEvidenceLinkFieldsMapToEvidenceApiParams(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(artifact_root, self._evidence_link_artifact())

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertEqual([], findings)

    def test_shouldRejectGrafanaArtifactWhenEvidenceLinkFieldIsMissingFromColumns(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['columns'] = [
                column for column in artifact['panels'][0]['targets'][0]['columns'] if column['selector'] != 'bucket_id'
            ]
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('evidenceLinkFields missing target columns: bucket_id' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWhenEvidenceLinkDoesNotMapRunBucketSeriesFields(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['fieldConfig']['defaults']['links'][0]['url'] = (
                '/api/charts/evidence/?scope_id=$scope_id&begin=$begin&end=$end&run=${__data.fields.run}'
                '&bucket=${__data.fields.bucket_id}&series=${__data.fields.series_name}'
            )
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('does not reference ${__data.fields.calculation_run_id}' in finding.message for finding in findings))
        self.assertTrue(any('must map run via run=${__data.fields.calculation_run_id}' in finding.message for finding in findings))

    def test_shouldRejectWideRenderArtifactThatUsesGenericLabelColumn(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['columns'][0] = {'selector': 'label', 'text': 'label'}
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('must not use generic label column' in finding.message for finding in findings))

    def test_shouldRejectChartDataArtifactUsingUnapprovedRenderRoot(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['root_selector'] = '$.points'
            artifact['panels'][0]['targets'][0]['metricsContract']['root'] = 'points'
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('render root' in finding.message and 'not approved' in finding.message for finding in findings))

    def test_shouldRejectChartDataArtifactUsingUnapprovedRenderShape(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['metricsContract']['shape'] = 'single_bug_trend_only'
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('render shape' in finding.message and 'not approved' in finding.message for finding in findings))

    def test_shouldRejectChartDataArtifactUsingUnapprovedContractVersion(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['metricsContract']['contractVersion'] = '9.9'
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('contractVersion' in finding.message and 'not approved' in finding.message for finding in findings))

    def test_shouldRejectChartDataArtifactWhenContractChartIdDoesNotMatchTarget(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['metricsContract']['chartId'] = 'other_chart'
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('metricsContract chartId must match target chart_id' in finding.message for finding in findings))

    def test_shouldRejectWideRenderArtifactWithNoValueFields(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['targets'][0]['metricsContract']['valueFields'] = []
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('valueFields must not be empty' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWhenEvidenceLinkOmitsChartId(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            artifact = self._evidence_link_artifact()
            artifact['panels'][0]['fieldConfig']['defaults']['links'][0]['url'] = artifact['panels'][0]['fieldConfig']['defaults']['links'][0]['url'].replace('&chart_id=default_bug_trend', '')
            self._write_artifact(artifact_root, artifact)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('evidence link URL must include chart_id' in finding.message for finding in findings))


    def test_shouldRejectEmptyArtifactRoot(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertEqual('no Grafana JSON artifacts found', findings[0].message)

    def _write_artifact(self, artifact_root, payload):
        artifact_path = artifact_root / 'bug_trend_dashboard.json'
        artifact_path.write_text(json.dumps(payload), encoding='utf-8')

    def _evidence_link_artifact(self):
        return {
            'panels': [
                {
                    'datasource': {'uid': 'metrics-bug-trend-api'},
                    'targets': [
                        {
                            'url': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end&chart_id=default_bug_trend',
                            'root_selector': '$.grafana_rows',
                            'columns': [
                                {'selector': 'bucket_label', 'text': 'bucket_label'},
                                {'selector': 'bucket_start', 'text': 'bucket_start'},
                                {'selector': 'bucket_end', 'text': 'bucket_end'},
                                {'selector': 'bucket_granularity', 'text': 'bucket_granularity'},
                                {'selector': 'calculation_run_id', 'text': 'calculation_run_id'},
                                {'selector': 'bucket_id', 'text': 'bucket_id'},
                                {'selector': 'all_open_bugs', 'text': 'all_open_bugs'},
                                {'selector': 'fixed_or_closed_bugs', 'text': 'fixed_or_closed_bugs'},
                            ],
                            'metricsContract': {
                                'chartId': 'default_bug_trend',
                                'contractVersion': '0.1',
                                'root': 'grafana_rows',
                                'shape': 'wide_bucket_series',
                                'categoryField': 'bucket_label',
                                'requiredFields': ['calculation_run_id', 'bucket_id', 'bucket_label', 'bucket_start', 'bucket_end', 'bucket_granularity'],
                                'valueFields': ['all_open_bugs', 'fixed_or_closed_bugs'],
                                'evidenceLinkFields': ['calculation_run_id', 'bucket_id'],
                                'seriesFieldSource': '__field.name',
                            },
                        }
                    ],
                    'fieldConfig': {
                        'defaults': {
                            'links': [
                                {
                                    'url': '/api/charts/evidence/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=default_bug_trend&run=${__data.fields.calculation_run_id}&bucket=${__data.fields.bucket_id}&series=${__field.name}'
                                }
                            ]
                        }
                    },
                }
            ]
        }