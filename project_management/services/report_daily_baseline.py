from project_management.app.domain.report_contracts import ReportError
from project_management.services.report_publication_reads import ReportPublicationReader


def assert_daily_baseline_current(repository, draft_or_context):
    draft = draft_or_context if hasattr(draft_or_context, 'authoring_context') else None
    authoring_context = draft_or_context.authoring_context if draft is not None else draft_or_context
    if authoring_context is None or authoring_context.get('report_role') != 'daily':
        return
    head = verified_daily_head(repository, authoring_context['series_id'])
    expected = authoring_context['base_daily_publication']
    if draft is not None and draft.selection.parent_publication_id is not None:
        _assert_linked_parent_current(repository, draft, authoring_context, head, expected)
        return
    if expected is None:
        if head is not None:
            raise ReportError('REPORT_BASELINE_CONFLICT')
        return
    if head is None or publication_ref(head) != expected:
        raise ReportError('REPORT_BASELINE_CONFLICT')


def _assert_linked_parent_current(repository, draft, context, head, expected):
    if expected is None or expected.get('publication_id') != draft.selection.parent_publication_id:
        raise ReportError('REPORT_BASELINE_CONFLICT')
    parent = ReportPublicationReader(repository).get(expected['publication_id'], repository.owner_subject)
    if publication_ref(parent) != expected or parent.manifest.series_id != context['series_id']:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    if head is None:
        raise ReportError('REPORT_BASELINE_CONFLICT')
    parent_date = _meeting_date(parent.manifest.meeting_key)
    head_date = _meeting_date(head.manifest.meeting_key)
    if parent_date == head_date and publication_ref(head) != expected:
        raise ReportError('REPORT_BASELINE_CONFLICT')
    if parent_date > head_date:
        raise ReportError('REPORT_BASELINE_CONFLICT')


def verified_daily_head(repository, series_id):
    reader = ReportPublicationReader(repository)
    publications = []
    for publication_id in repository.list_report_publication_ids(limit=500):
        publication = reader.get(publication_id, repository.owner_subject)
        manifest = publication.manifest
        if (manifest.schema_version == 2 and manifest.report_role == 'daily'
                and manifest.series_id == series_id and manifest.purpose == 'standup'):
            publications.append(publication)
    if not publications:
        return None
    return select_daily_head(publications)


def select_daily_head(publications):
    publications = tuple(publications)
    if not publications:
        return None
    return max(publications, key=lambda item: (_meeting_date(item.manifest.meeting_key), item.manifest.finalized_at, item.manifest.publication_id))


def publication_ref(publication):
    return {
        'publication_id': publication.manifest.publication_id,
        'manifest_hash': publication.manifest_sha256,
        'commit': publication.commit_id,
    }


def _meeting_date(meeting_key):
    parts = str(meeting_key).split(':')
    if len(parts) != 3:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return parts[2]
