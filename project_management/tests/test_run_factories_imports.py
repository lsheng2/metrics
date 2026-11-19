import importlib
from pathlib import Path


PRODUCTION_PATHS = [
    Path('metrics/settings/defaults_metrics.py'),
    Path('project_management/app/api/run_factories.py'),
    Path('project_management/app/api/summary_analysis.py'),
    Path('project_management/app/domain/summary_contracts.py'),
    Path('project_management/services/report_assists.py'),
    Path('project_management/services/summary_analysis.py'),
    Path('project_management/services/summary_journal_reads.py'),
]


def test_shouldImportRunFactoriesWithoutLegacyHttpSdkInstalled():
    module = importlib.import_module('project_management.app.api.run_factories')

    assert hasattr(module, 'build_project_runtime')


def test_shouldImportReportAssistsWithoutLegacyHttpSdkInstalled():
    module = importlib.import_module('project_management.services.report_assists')

    assert hasattr(module, 'ReportAssistService')


def test_shouldImportSummaryAnalysisWithoutLegacyHttpSdkInstalled():
    module = importlib.import_module('project_management.services.summary_analysis')

    assert hasattr(module, 'SummaryAnalysisService')


def test_shouldHaveNoProductionLegacySdkCompatibilityPath():
    forbidden = (
        'ai_base_application_sdk',
        'TaskRunClient',
        'TaskRunClientError',
        'AiBackendTarget',
        'validate_backend',
        'execution_mode',
        'METRICS_PROJECT_RUNTIME_FACTORY',
        'METRICS_PROJECT_AI_',
        'METRICS_REPORT_ASSIST_FACTORY',
        'METRICS_AI_SIDECAR_ENABLED',
        'METRICS_AI_BASE_',
        'ai_bundle',
        '_legacy_task_run_client_error_types',
        '_is_legacy_task_run_client_error',
    )

    for path in PRODUCTION_PATHS:
        content = path.read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in content, f'{token} remains in {path}'


def test_shouldRemoveRetiredSdkArtifactsAndBundleEntries():
    assert not Path('requirements-ai-task.txt').exists()
    assert not Path('project_management/ai_bundle').exists()
    assert not Path('scripts/validation/run_project_sdk_preintegration.py').exists()
    assert not Path('project_management/out/ai_task_contract.py').exists()
    assert not Path('project_management/out/report_ai_task.py').exists()

    attributes = Path('.gitattributes').read_text(encoding='utf-8')
    assert 'project_management/ai_bundle' not in attributes

    env_example = Path('.env.example').read_text(encoding='utf-8')
    for token in ('METRICS_PROJECT_AI_', 'project_serve', 'METRICS_AI_BASE_', 'METRICS_AI_SIDECAR_ENABLED'):
        assert token not in env_example
    assert 'manage.py serve' in env_example
