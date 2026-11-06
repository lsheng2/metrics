from functools import lru_cache
from pathlib import Path

from django.conf import settings

from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.out.ai_task_contract import AiTaskContract
from project_management.out.report_ai_task import AuthoringTaskContract
from project_management.out.preparation_links import DjangoPreparationLinkBuilder
from project_management.reporting.html import ReportRenderer
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_continuity import ReportContinuityService
from project_management.services.report_drafts import ReportDraftService
from project_management.services.report_preparation import ReportPreparationService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.services.report_assist_receipts import ReportAssistReceiptVerifier
from project_management.services.report_sources import ReportSourceReader
from project_management.services.report_templates import ReportTemplateService
from project_management.services.project_runs import ProjectRunService
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from provider_sync.app.api.references import create_provider_reference_reader
from project_management.services.report_queries import ReportQueryService


PACK_ROOT = (
    Path(__file__).resolve().parents[2]
    / 'ai_bundle'
    / 'strict-summary'
    / 'task-run-contract-0.1.0a2'
)


def build_report_query_service(*, archive=None, draft_service=None):
    archive = archive or build_capture_archive_service()
    return ReportQueryService(archive, draft_service or build_report_service(archive=archive))


def build_report_service(*, project_api=None, archive=None, contract=None, renderer=None, template_service=None) -> ReportDraftService:
    project_api = project_api or build_project_api()
    archive = archive or build_capture_archive_service(project_api=project_api)
    contract = contract or _default_contract()
    renderer = renderer or ReportRenderer()
    return ReportDraftService(
        archive,
        ReportSourceReader(archive, contract),
        renderer,
        reference_verifier=ReferenceReceiptVerifier(settings.SECRET_KEY),
        assist_verifier=ReportAssistReceiptVerifier(contract_loader=_authoring_contract),
        template_service=template_service,
    )


def build_report_template_service(*, limits=None, clock=None) -> ReportTemplateService:
    return ReportTemplateService(limits=limits, clock=clock)


def build_report_continuity_service(*, project_api=None, archive=None, contract=None,
                                    template_service=None, limits=None, clock=None) -> ReportContinuityService:
    project_api = project_api or build_project_api()
    archive = archive or build_capture_archive_service(project_api=project_api)
    contract = contract or _default_contract()
    return ReportContinuityService(
        archive,
        ReportSourceReader(archive, contract),
        template_service=template_service,
        limits=limits,
        clock=clock,
    )


def build_report_preparation_service(*, project_api=None, archive=None, contract=None, renderer=None,
                                     template_service=None, continuity_service=None,
                                     draft_service=None, run_service=None) -> ReportPreparationService:
    project_api = project_api or build_project_api()
    archive = archive or build_capture_archive_service(project_api=project_api)
    contract = contract or _default_contract()
    template_service = template_service or build_report_template_service()
    continuity_service = continuity_service or build_report_continuity_service(
        project_api=project_api,
        archive=archive,
        contract=contract,
        template_service=template_service,
    )
    draft_service = draft_service or build_report_service(
        project_api=project_api,
        archive=archive,
        contract=contract,
        renderer=renderer,
        template_service=template_service,
    )
    if run_service is None:
        run_service = ProjectRunService(project_api, archive, None, None, draft_service, None)
    return ReportPreparationService(
        continuity_service,
        draft_service,
        template_service,
        link_builder=DjangoPreparationLinkBuilder(),
        run_service=run_service,
    )


def build_report_preparation_for_run(run_service) -> ReportPreparationService:
    draft_service = run_service.draft_service
    template_service = draft_service.template_service
    continuity = ReportContinuityService(
        run_service.archive,
        draft_service.source_reader,
        template_service=template_service,
        clock=draft_service.clock,
    )
    return ReportPreparationService(
        continuity, draft_service, template_service,
        link_builder=DjangoPreparationLinkBuilder(), run_service=run_service,
    )


def build_report_completion_service(*, project_api=None, archive=None, contract=None, renderer=None,
                                    reference_reader=None) -> ReportCompletionService:
    project_api = project_api or build_project_api()
    archive = archive or build_capture_archive_service(project_api=project_api)
    contract = contract or _default_contract()
    source_reader = ReportSourceReader(archive, contract)
    verifier = ReferenceReceiptVerifier(settings.SECRET_KEY)
    return ReportCompletionService(
        ReportDraftService(archive, source_reader, renderer or ReportRenderer(), reference_verifier=verifier),
        source_reader,
        create_provider_reference_reader(reader=reference_reader),
        verifier,
        CompletionAdmissionStore(archive.config.root),
    )


@lru_cache(maxsize=1)
def _default_contract():
    return AiTaskContract.load(PACK_ROOT)


@lru_cache(maxsize=1)
def _authoring_contract():
    return AuthoringTaskContract.load(PACK_ROOT)


def build_report_assist_service(*, draft_service=None):
    from django.utils.module_loading import import_string
    from project_management.services.report_assists import ReportAssistService
    from project_management.app.domain.report_contracts import ReportError
    from project_management.app.domain.summary_contracts import AnalysisError

    draft_service = draft_service or build_report_service()
    try:
        contract = _authoring_contract()
    except AnalysisError:
        raise ReportError('REPORT_AI_UNAVAILABLE') from None
    factory = getattr(settings, 'METRICS_REPORT_ASSIST_FACTORY', None)
    if factory is None:
        return ReportAssistService(draft_service, contract)
    if isinstance(factory, str):
        factory = import_string(factory)
    service = factory(draft_service=draft_service, contract=contract)
    if (not isinstance(service, ReportAssistService) or service.drafts is not draft_service
            or service.contract.definition_hash != contract.definition_hash):
        raise ReportError('REPORT_AI_UNAVAILABLE')
    return service
