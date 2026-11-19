from django.conf import settings

from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.app.api.report_factories import build_report_preparation_for_run, build_report_service
from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.domain.run_contracts import RunError, RunPolicy
from project_management.runtime import ProjectRunRuntime
from project_management.services.capture import ProjectCaptureService
from project_management.services.project_runs import ProjectRunService
from project_management.services.project_run_worker import ProjectRunWorker
from project_management.services.summary_analysis import SummaryAnalysisService
from project_management.services.task_contracts import SummaryTaskContract
from provider_sync.app.api.access_factory import capture_limits_from_settings, create_provider_access_service


def build_run_read_service():
    project_api = build_project_api()
    archive = build_capture_archive_service(project_api=project_api)
    draft_service = build_report_service(project_api=project_api, archive=archive)
    return ProjectRunService(
        project_api,
        archive,
        None,
        None,
        draft_service,
        None,
        policy=_policy_from_settings(settings),
        capture_limits=capture_limits_from_settings(settings),
        notifier=None,
    )


def build_project_runtime(*, task_runs, principal_resolver):
    if (not getattr(settings, 'METRICS_PROJECT_RUN_ENABLED', False)
            or task_runs is None or not callable(principal_resolver)):
        raise RunError('RUN_UNAVAILABLE')
    project_api = build_project_api()
    archive = build_capture_archive_service(project_api=project_api)
    contract = SummaryTaskContract(load_task_profile('metrics.project_summary'))
    draft_service = build_report_service(project_api=project_api, archive=archive, contract=contract)
    capture = ProjectCaptureService(project_api, create_provider_access_service(), archive)
    analysis = SummaryAnalysisService(archive, contract, task_runs)
    service = ProjectRunService(
        project_api, archive, capture, analysis, draft_service, principal_resolver,
        task_profile=contract.profile, policy=_policy_from_settings(settings),
        capture_limits=capture_limits_from_settings(settings),
    )
    worker = ProjectRunWorker(service, daily_preparation_service=build_report_preparation_for_run(service))
    return ProjectRunRuntime(service, worker)


def _policy_from_settings(source):
    return RunPolicy(
        timeout_seconds=getattr(source, 'METRICS_PROJECT_RUN_TIMEOUT_SECONDS', 600),
        max_analysis_items=getattr(source, 'METRICS_PROJECT_RUN_MAX_ANALYSIS_ITEMS', 10),
        max_observations_per_attempt=getattr(source, 'METRICS_PROJECT_RUN_MAX_OBSERVATIONS_PER_ATTEMPT', 16),
        max_queued_operations=getattr(source, 'METRICS_PROJECT_RUN_MAX_QUEUED', 16),
    )
