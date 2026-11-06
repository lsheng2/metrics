from project_management.app.domain.report_authoring import AUTHORING_SCHEMA
from project_management.app.domain.report_templates import is_pinned_renderer


def render_edits(draft):
    if draft.authoring_schema == AUTHORING_SCHEMA:
        return draft.authored_edits
    return draft.edits


def is_pinned_document(draft):
    return (
        draft.authoring_schema == AUTHORING_SCHEMA
        and isinstance(draft.template_snapshot, dict)
        and is_pinned_renderer(draft.template_snapshot.get('renderer_version'))
    )
