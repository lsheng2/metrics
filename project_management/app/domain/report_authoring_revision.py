from project_management.app.domain.report_authoring import validate_authored_edits, validate_template_snapshot
from project_management.app.domain.report_contracts import ReportError


def validate_revision_authoring_context(authoring_context, template_snapshot):
    snapshot = validate_template_snapshot(template_snapshot)
    document = snapshot['resolved_document']
    if authoring_context is None:
        if document['schema_version'] == 2:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return None
    if document['schema_version'] != 2:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
    return validate_daily_authoring_context(authoring_context)


def validate_authored_revision_payload(snapshot, payload):
    context = validate_revision_authoring_context(payload['authoring_context'], payload['template_snapshot'])
    if context is None:
        validate_authored_edits(snapshot, payload['edits'], payload['template_snapshot'])
    else:
        from project_management.app.domain.report_continuity_edits import validate_continuity_authored_edits
        continuity, standard = _split_context_edits(payload['edits'])
        validate_continuity_authored_edits(context, continuity)
        validate_authored_edits(snapshot, standard, payload['template_snapshot'])
    return context


def _split_context_edits(edits):
    continuity = []
    standard = []
    for edit in tuple(edits or ()):
        target = edit.target
        if isinstance(target, dict) and target.get('scope') in {'daily_note', 'report_action', 'persistent_note'}:
            continuity.append(edit)
        else:
            standard.append(edit)
    return tuple(continuity), tuple(standard)
