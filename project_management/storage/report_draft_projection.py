from project_management.app.domain.report_authoring import authored_edit_to_legacy
from project_management.app.domain.report_draft_values import ReportDraft


def draft_from_revision(payload, revision_hash, snapshot, state, preservation_review_issues=()):
    edits = tuple(authored_edit_to_legacy(edit) for edit in payload['edits']) if payload['schema_version'] == 2 else payload['edits']
    authored_edits = payload['edits'] if payload['schema_version'] == 2 else ()
    return ReportDraft(
        payload['draft_id'], payload['revision'], revision_hash, payload['selection'], payload['snapshot_hash'],
        snapshot, payload['template'], payload['template_definition'], edits,
        payload['created_at'], payload['updated_at'], payload['parent_publication_id'], state,
        payload.get('authoring_schema'), payload.get('template_snapshot'),
        authored_edits, payload.get('authoring_context'), tuple(preservation_review_issues),
    )
