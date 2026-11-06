from dataclasses import asdict

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity import PreparedContextRef
from project_management.services.report_continuity_seed_binding import seed_binding


def replay_prepared_context(service, existing, actor, project_id, stage_id, *,
                            preparation_id, create_command_id, draft_id, series_id,
                            series_policy_hash, expected_baseline_ref, selection,
                            template_use_hash, meeting, period, authority,
                            acknowledge_gap_draft_ids, preservation_parent_draft):
    if existing is None:
        return None
    preservation = existing.get('preservation')
    if preservation_parent_draft is not None:
        parent = preservation_parent_draft
        if (not preservation or preservation.get('source_kind') != 'parent_draft_revision'
                or preservation.get('parent_draft_id') != parent.draft_id
                or preservation.get('parent_draft_revision') != parent.revision
                or preservation.get('parent_draft_revision_hash') != parent.revision_hash):
            raise ReportError('REPORT_REVISION_CONFLICT')
    elif preservation is not None:
        baseline = {} if expected_baseline_ref is None else asdict(expected_baseline_ref)
        if (preservation.get('source_kind') != 'source_publication'
                or any(preservation.get(key) != value for key, value in baseline.items())
                or not baseline):
            raise ReportError('REPORT_REVISION_CONFLICT')
    expected = seed_binding(
        service, actor, project_id, stage_id, preparation_id, create_command_id,
        draft_id, series_id, series_policy_hash, expected_baseline_ref, selection,
        template_use_hash, meeting, period, authority, preservation,
    )
    service._verify_existing_seed(existing, expected)
    if tuple(existing['context']['acknowledged_gap_draft_ids']) != tuple(acknowledge_gap_draft_ids):
        raise ReportError('REPORT_REVISION_CONFLICT')
    return PreparedContextRef(existing['preparation_id'], existing['context_hash'], existing['draft_id'])
