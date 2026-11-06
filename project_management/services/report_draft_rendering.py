from project_management.app.domain.report_authoring import AUTHORING_SCHEMA


def render_edits(draft):
    if draft.authoring_schema == AUTHORING_SCHEMA:
        return draft.authored_edits
    return draft.edits


def is_pinned_document(draft):
    return (
        draft.authoring_schema == AUTHORING_SCHEMA
        and isinstance(draft.template_snapshot, dict)
        and draft.template_snapshot.get('renderer_version') == 'template-document/1'
    )
