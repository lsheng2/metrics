import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / 'scripts' / 'validate_grafana_artifacts.py'
ALLOWLIST_PATH = REPO_ROOT / 'openspec' / 'docs' / 'current-baseline' / 'grafana-approved-data-surfaces.json'

spec = spec_from_file_location('validate_grafana_artifacts_query', VALIDATOR_PATH)
validate_grafana_artifacts = module_from_spec(spec)
sys.modules[spec.name] = validate_grafana_artifacts
spec.loader.exec_module(validate_grafana_artifacts)


class TestGrafanaQuerySurfaceContract(TestCase):
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
                                {'path': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end&run=$run'}
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
                                {'path': '/api/charts/data/?scope_id=$scope'}
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
                                {'path': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end'}
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
                                {'path': '/api/charts/data/internal-secret/?scope_id=$scope&begin=$begin&end=$end'}
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
                                {'url': 'http://metrics.local/api/charts/data/internal-secret/?scope_id=$scope&begin=$begin&end=$end'}
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
                                {'url': 'https://evil.example/api/charts/data/?scope_id=$scope&begin=$begin&end=$end'}
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
                                {'path': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end&status=Fixed&priority=P1-Stopper'}
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

    def test_shouldRejectProviderNeutralSurfaceWithNativeQueryParams(self):
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
                                    'path': '/api/provider-charts/data/?provider_id=jira&profile_id=chiplet-2a-jira&begin_ww=25WW15&end_ww=26WW32&chart_id=open_bugs_trend&jql=project%20%3D%20131600&hsdes_subject=ip_fw_sw_sensing.bug'
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
        self.assertTrue(any('unapproved Metrics API query params' in finding.message for finding in findings))

    def test_shouldRejectGrafanaTargetWithRawJqlQueryLiteral(self):
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
                                {'query': 'project = "131600" AND component = "team_int_qemu"'}
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
        self.assertTrue(any('provider-native query or field literal' in finding.message for finding in findings))

    def test_shouldRejectGrafanaTargetWithHsdesArticleFieldLiteral(self):
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
                                {'query': 'subject = ip_fw_sw_sensing.bug and HSD_type = bug'}
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
        self.assertTrue(any('provider-native query or field literal' in finding.message for finding in findings))

    def test_shouldRejectGrafanaTargetWithJiraCustomFieldLiteral(self):
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
                                {'query': 'customfield_12345 = 2a'}
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
        self.assertTrue(any('provider-native query or field literal' in finding.message for finding in findings))

    def test_shouldApproveProviderProfileReadinessSurface(self):
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
                                    'url': '/api/provider-profiles/readiness/?profile_id=$profile_id',
                                    'root_selector': '$.profile_status_rows',
                                    'columns': [
                                        {'selector': 'provider_id', 'text': 'provider_id'},
                                        {'selector': 'profile_id', 'text': 'profile_id'},
                                        {'selector': 'status', 'text': 'status'},
                                        {'selector': 'data_status', 'text': 'data_status'},
                                        {'selector': 'data_status_reason', 'text': 'data_status_reason'},
                                        {'selector': 'auth_action_label', 'text': 'auth_action_label'},
                                        {'selector': 'auth_action_url', 'text': 'auth_action_url'},
                                    ],
                                    'metricsContract': {
                                        'contractVersion': '0.2',
                                        'semanticOwner': 'metrics',
                                        'root': 'profile_status_rows',
                                        'shape': 'profile_readiness_summary',
                                        'evidenceCapability': 'summary_only',
                                        'evidenceLinkFields': [],
                                        'requiredFields': ['provider_id', 'profile_id', 'status', 'data_status', 'data_status_reason', 'auth_action_label', 'auth_action_url'],
                                    },
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

    def test_shouldRejectDailyMetricPanelWithGrafanaCalculationTransform(self):
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
                                    'url': '/api/provider-charts/data/?profile_id=$profile&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=daily_new_standard_bug_count&chart_version=1',
                                    'root_selector': '$.grafana_rows',
                                    'columns': [
                                        {'selector': 'provider_id', 'text': 'provider_id'},
                                        {'selector': 'profile_id', 'text': 'profile_id'},
                                        {'selector': 'calculation_run_id', 'text': 'calculation_run_id'},
                                        {'selector': 'fact_snapshot_id', 'text': 'fact_snapshot_id'},
                                        {'selector': 'bucket_label', 'text': 'bucket_label'},
                                        {'selector': 'bucket_start', 'text': 'bucket_start'},
                                        {'selector': 'bucket_end', 'text': 'bucket_end'},
                                        {'selector': 'bucket_granularity', 'text': 'bucket_granularity'},
                                        {'selector': 'mapping_version', 'text': 'mapping_version'},
                                        {'selector': 'new_standard_bugs', 'text': 'new_standard_bugs'},
                                    ],
                                    'metricsContract': {
                                        'chartId': 'daily_new_standard_bug_count',
                                        'contractVersion': '0.2',
                                        'semanticOwner': 'metrics',
                                        'chartRecipeId': 'daily_new_standard_bug_count',
                                        'chartRecipeVersion': 1,
                                        'providerBinding': 'selected_provider_quality',
                                        'calculationOwner': 'metrics',
                                        'aggregationOwner': 'materialized_aggregate',
                                        'bucketGrain': 'day',
                                        'root': 'grafana_rows',
                                        'shape': 'wide_bucket_series',
                                        'categoryField': 'bucket_label',
                                        'requiredFields': ['provider_id', 'profile_id', 'calculation_run_id', 'fact_snapshot_id', 'bucket_label', 'bucket_start', 'bucket_end', 'bucket_granularity', 'mapping_version'],
                                        'valueFields': ['new_standard_bugs'],
                                    },
                                }
                            ],
                            'transformations': [{'id': 'calculateField'}],
                        }
                    ]
                },
            )

            # When
            findings = validate_grafana_artifacts.validate_artifact_root(
                artifact_root, validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH)
            )

        # Then
        self.assertTrue(any('daily metric panels must not use Grafana calculation transformations' in finding.message for finding in findings))

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
                                {'path': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end'}
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
                                {'path': '/api/charts/data/?scope_id=$scope&begin=$begin&end=$end'}
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

    def _write_artifact(self, artifact_root, payload):
        artifact_path = artifact_root / 'bug_trend_dashboard.json'
        artifact_path.write_text(json.dumps(payload), encoding='utf-8')
