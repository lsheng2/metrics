from ai_base_application_sdk import TaskRunClient
from django.conf import settings
import httpx

from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.app.api.report_factories import build_report_service
from project_management.app.domain.run_contracts import RunError, RunPolicy
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.runtime import ProjectRunRuntime
from project_management.services.project_runs import ProjectRunService
from provider_sync.app.api.access_factory import capture_limits_from_settings


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
        _offline_backend_resolver(),
        policy=_policy_from_settings(settings),
        capture_limits=capture_limits_from_settings(settings),
        notifier=None,
    )


def build_project_runtime():
    factory = getattr(settings, 'METRICS_PROJECT_RUNTIME_FACTORY', None)
    if factory is not None:
        runtime = factory()
        if not isinstance(runtime, ProjectRunRuntime):
            raise RunError('RUN_INVALID')
        return runtime
    raise RunError('RUN_UNAVAILABLE')


def _policy_from_settings(source):
    return RunPolicy(
        timeout_seconds=getattr(source, 'METRICS_PROJECT_RUN_TIMEOUT_SECONDS', 600),
        max_analysis_items=getattr(source, 'METRICS_PROJECT_RUN_MAX_ANALYSIS_ITEMS', 10),
        max_observations_per_attempt=getattr(source, 'METRICS_PROJECT_RUN_MAX_OBSERVATIONS_PER_ATTEMPT', 16),
        max_queued_operations=getattr(source, 'METRICS_PROJECT_RUN_MAX_QUEUED', 16),
    )


def _backend_resolver_from_settings(source):
    target = getattr(source, 'METRICS_PROJECT_AI_TARGET', {}) or {}
    if not isinstance(target, dict):
        raise RunError('RUN_INVALID')
    mode = target.get('execution_mode', 'synthetic')
    if mode != 'synthetic':
        raise RunError('RUN_UNAVAILABLE')

    def resolve(actor, project_id, stage_id):
        return AiBackendTarget(
            _text(target.get('base_url')),
            _text(target.get('source_app_id')),
            _text(target.get('run_store_id')),
            f'projects.{project_id}.stages.{stage_id}',
            _text(target.get('grant_revision')),
            _text(target.get('limit_policy_revision')),
        )

    return resolve


def _offline_backend_resolver():
    def resolve(actor, project_id, stage_id):
        raise RunError('RUN_UNAVAILABLE')

    return resolve


def _client_factory_from_settings(source):
    credential_ref = getattr(source, 'METRICS_PROJECT_AI_CREDENTIAL_REF', '')
    token = getattr(source, 'METRICS_PROJECT_AI_TOKEN', '')
    if not credential_ref or not token:
        raise RunError('RUN_UNAVAILABLE')

    def factory(backend):
        return TaskRunClient(
            base_url=backend.base_url,
            source_app_id=backend.source_app_id,
            run_store_id=backend.run_store_id,
            credential_ref=credential_ref,
            token=token,
            transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
        )

    return factory


def _text(value):
    if type(value) is not str or not value.strip():
        raise RunError('RUN_UNAVAILABLE')
    return value.strip()
