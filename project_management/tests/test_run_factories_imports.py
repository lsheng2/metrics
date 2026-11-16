import importlib
from pathlib import Path


PRODUCTION_PATHS = [
    Path('project_management/app/api/run_factories.py'),
    Path('project_management/services/report_assists.py'),
    Path('project_management/services/summary_analysis.py'),
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
        '_legacy_task_run_client_error_types',
        '_is_legacy_task_run_client_error',
    )

    for path in PRODUCTION_PATHS:
        content = path.read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in content, f'{token} remains in {path}'
