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
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'metrics-bug-trend-api'},
                            'targets': [
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end&chart_id=default_bug_trend'}
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
                                    'path': '/api/bug-trend/evidence/?scope_id=$scope&begin=$begin&end=$end&run=$run&bucket=$bucket&series=$series&chart_id=default_bug_trend'
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
                '/api/bug-trend/evidence/?scope_id=$scope_id&begin=$begin&end=$end&run=${__data.fields.run}'
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


    def test_shouldRejectChartDataArtifactWithEvidenceOnlyParams(self):
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
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end&run=$run'}
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
        self.assertTrue(any('unapproved Metrics API query params' in finding.message for finding in findings))

    def test_shouldRejectChartDataArtifactMissingRequiredParams(self):
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
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope'}
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
        self.assertTrue(any('missing required Metrics API query params' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithQueryAndNoExplicitDatasource(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'targets': [
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('has no explicit approved datasource' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithUnapprovedApiPathPrefixCollision(self):
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
                                {'path': '/api/bug-trend/chart-data/internal-secret/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('unapproved Metrics API path' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithUnapprovedFullUrlApiPath(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'targets': [
                                {'url': 'http://metrics.local/api/bug-trend/chart-data/internal-secret/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('has no explicit approved datasource' in finding.message for finding in findings))
        self.assertTrue(any('unapproved Metrics API path' in finding.message for finding in findings))
        self.assertTrue(any('must be a relative path' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithExternalHostEvenWhenApiPathIsApproved(self):
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
                                {'url': 'https://evil.example/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('must be a relative path' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithHardcodedSemanticQueryParams(self):
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
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end&status=Fixed&priority=P1-Stopper'}
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
        self.assertTrue(any('unapproved Metrics API query params' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactThatReadsRawJiraTables(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'metrics-bug-trend-api'},
                            'targets': [{'rawSql': 'SELECT key FROM jira_history_jiraissue'}],
                        }
                    ]
                },
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('SQL datasource disabled for current phase' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactThatDuplicatesLifecycleSemantics(self):
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
                                    'rawSql': "SELECT CASE WHEN status = 'Fixed' THEN 1 ELSE 0 END FROM bug_trend_bucket_fact_v1"
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
        self.assertTrue(any('SQL datasource disabled for current phase' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithSqlQueryEvenWithoutTables(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'metrics-bug-trend-api'},
                            'targets': [{'rawSql': 'SELECT 1 AS value'}],
                        }
                    ]
                },
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('SQL datasource disabled for current phase' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithUnapprovedDatasource(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': {'uid': 'default-postgres'},
                            'targets': [
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('unapproved datasource uid' in finding.message for finding in findings))

    def test_shouldRejectGrafanaArtifactWithUnapprovedStringDatasource(self):
        # Given
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir)
            self._write_artifact(
                artifact_root,
                {
                    'panels': [
                        {
                            'datasource': 'default-postgres',
                            'targets': [
                                {'path': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end'}
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
        self.assertTrue(any('unapproved datasource uid' in finding.message for finding in findings))

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
                            'url': '/api/bug-trend/chart-data/?scope_id=$scope&begin=$begin&end=$end&chart_id=default_bug_trend',
                            'columns': [
                                {'selector': 'label', 'text': 'label'},
                                {'selector': 'calculation_run_id', 'text': 'calculation_run_id'},
                                {'selector': 'bucket_id', 'text': 'bucket_id'},
                                {'selector': 'series_name', 'text': 'series_name'},
                            ],
                            'metricsContract': {
                                'evidenceLinkFields': ['calculation_run_id', 'bucket_id', 'series_name'],
                            },
                        }
                    ],
                    'fieldConfig': {
                        'defaults': {
                            'links': [
                                {
                                    'url': '/api/bug-trend/evidence/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=default_bug_trend&run=${__data.fields.calculation_run_id}&bucket=${__data.fields.bucket_id}&series=${__data.fields.series_name}'
                                }
                            ]
                        }
                    },
                }
            ]
        }