from functools import lru_cache
from pathlib import Path

from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.out.ai_task_contract import AiTaskContract
from project_management.reporting.html import ReportRenderer
from project_management.services.report_drafts import ReportDraftService
from project_management.services.report_sources import ReportSourceReader


PACK_ROOT = (
    Path(__file__).resolve().parents[2]
    / 'ai_bundle'
    / 'strict-summary'
    / 'task-run-contract-0.1.0a2'
)


def build_report_service(*, project_api=None, archive=None, contract=None, renderer=None) -> ReportDraftService:
    project_api = project_api or build_project_api()
    archive = archive or build_capture_archive_service(project_api=project_api)
    contract = contract or _default_contract()
    renderer = renderer or ReportRenderer()
    return ReportDraftService(archive, ReportSourceReader(archive, contract), renderer)


@lru_cache(maxsize=1)
def _default_contract():
    return AiTaskContract.load(PACK_ROOT)
