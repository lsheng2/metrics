from project_management.app.domain.capture_values import decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import ReportDraftLimits
from project_management.services.report_preparation_seed import validate_prepared_context_seed
from project_management.services.report_publication_reads import ReportPublicationReader
from project_management.storage.paths import inspect_components, read_bytes
from project_management.storage.report_drafts import ReportDraftStore
from project_management.storage.report_preparations import ReportPreparationStore


def occupied_meetings(repository, archive, series_id, dates):
    if repository is None:
        return {}
    wanted = set(dates)
    occupied = {}
    preparations = ReportPreparationStore(repository, archive.config.root, archive.config.limits)
    for path in _directories(repository.runtime / 'report-preparations'):
        intent = preparations.find_intent(path.name)
        if intent is not None:
            _add(occupied, wanted, series_id, intent['series_id'], intent['meeting_date'], path.name)
        seed_path = f'report-preparations/{path.name}/context.json'
        if (repository.runtime / seed_path).exists():
            seed = decode_json(read_bytes(repository.runtime, seed_path))
            context = validate_prepared_context_seed(seed)
            _add_context(occupied, wanted, series_id, context, seed['draft_id'])
    drafts = ReportDraftStore(repository, archive.config.root, archive.config.limits, ReportDraftLimits())
    for path in _directories(repository.runtime / 'report-drafts'):
        draft = drafts.read_draft(path.name)
        _add_context(occupied, wanted, series_id, draft.authoring_context, draft.draft_id)
    reader = ReportPublicationReader(repository)
    for publication_id in repository.list_report_publication_ids(limit=500):
        publication = reader.get(publication_id, repository.owner_subject)
        manifest = publication.manifest
        if manifest.schema_version == 2 and manifest.report_role == 'daily':
            _add(occupied, wanted, series_id, manifest.series_id,
                 manifest.meeting_key.rsplit(':', 1)[-1], publication_id)
    return occupied


def _directories(root):
    inspect_components(root)
    if not root.exists():
        return ()
    if not root.is_dir():
        raise ReportError('REPORT_ARTIFACT_INVALID')
    result = []
    try:
        for path in root.iterdir():
            inspect_components(path)
            if not path.is_dir():
                raise ReportError('REPORT_ARTIFACT_INVALID')
            result.append(path)
            if len(result) > 500:
                raise ReportError('REPORT_LIMIT')
    except (OSError, ArchiveError):
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    return tuple(result)


def _add_context(occupied, dates, series_id, context, work_id):
    if context is not None and context.get('report_role') == 'daily':
        _add(occupied, dates, series_id, context['series_id'], context['meeting']['local_date'], work_id)


def _add(occupied, dates, expected_series, series_id, local_date, work_id):
    if series_id == expected_series and local_date in dates:
        occupied[local_date] = work_id
