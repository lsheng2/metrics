from dataclasses import asdict

from project_management.app.domain.report_continuity import (
    PublicationRef,
    meeting_identity,
    meeting_key,
    period_identity,
    period_key,
)
from project_management.app.domain.report_draft_values import ReportDraftLimits
from project_management.app.domain.report_preparation import BaselinePreview
from project_management.services.report_daily_baseline import publication_ref, verified_daily_head
from project_management.storage.report_drafts import ReportDraftStore


def build_baseline_preview(archive, actor, project_id, stage_id, policy, meeting_date):
    if archive is None:
        meeting = meeting_identity(policy.calendar, meeting_date)
        period = period_identity(meeting)
        return _preview(policy, meeting, period, None, ())
    with archive._report_read_view(actor, project_id, stage_id, allow_absent=True) as repository:
        if repository is None:
            meeting = meeting_identity(policy.calendar, meeting_date)
            return _preview(policy, meeting, period_identity(meeting), None, ())
        return build_baseline_preview_from_repository(archive, repository, policy, meeting_date)


def build_baseline_preview_from_repository(archive, repository, policy, meeting_date):
    with repository.open_read_view() as view:
        return _preview_from_view(archive, view, policy, meeting_date)


def _preview_from_view(archive, repository, policy, meeting_date):
    meeting = meeting_identity(policy.calendar, meeting_date)
    period = period_identity(meeting)
    head = verified_daily_head(repository, policy.series_id)
    baseline = None if head is None else PublicationRef(**publication_ref(head))
    pending = _pending_gap_drafts(archive, repository, policy.series_id, meeting.local_date)
    return _preview(policy, meeting, period, baseline, pending)


def _preview(policy, meeting, period, baseline, pending):
    state = 'pending' if pending else ('ready' if baseline is not None else 'initial')
    return BaselinePreview(
        state,
        policy.series_id,
        policy.revision_hash,
        meeting_key(meeting),
        period_key(period),
        baseline,
        pending,
        (asdict(policy.default_template_selection),),
        ('saved_capture',),
        ('manual_only',),
    )


def _pending_gap_drafts(archive, repository, series_id, local_date):
    root = repository.runtime / 'report-drafts'
    if not root.exists():
        return ()
    store = ReportDraftStore(repository, archive.config.root, archive.config.limits, ReportDraftLimits())
    pending = []
    ids = tuple(path.name for path in sorted(root.iterdir()) if path.is_dir())
    for draft in repository.map_reads(store.read_draft, ids):
        _append_pending(pending, draft, series_id, local_date)
    return tuple(item[1] for item in sorted(pending))


def _append_pending(pending, draft, series_id, local_date):
    context = draft.authoring_context
    if (context is not None and context.get('report_role') == 'daily'
            and context.get('series_id') == series_id
            and context.get('meeting', {}).get('local_date') < local_date
            and draft.state != 'finalized'):
        pending.append((context['meeting']['local_date'], draft.draft_id))
