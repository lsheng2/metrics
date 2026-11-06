from django.http import JsonResponse

from project_management.app.api import reports as report_api
from ui_web.project_access import private_no_store
from ui_web.report_authoring_forms import ReportAuthoredSaveForm


def wants_json(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
    )


def authored_json_error(error, *, form=None, draft=None):
    response = {
        'state': 'failed',
        'error_code': getattr(error, 'code', 'REPORT_INVALID'),
        'message': str(error),
        'submitted_edits': (),
    }
    if isinstance(form, ReportAuthoredSaveForm):
        response['form_errors'] = form.errors.get_json_data()
        try:
            response['submitted_edits'] = form.submitted_edits()
        except Exception:
            response['submitted_edits'] = ()
    if draft is not None:
        response['revision'] = draft.revision
        response['revision_hash'] = draft.revision_hash
    return private_no_store(JsonResponse(response, status=report_status(error)))


def report_status(error):
    if error.code == 'REPORT_NOT_FOUND':
        return 404
    if error.code in {
        'REPORT_REVISION_CONFLICT', 'REPORT_SOURCE_CHANGED', 'REPORT_COMPARISON_UNAVAILABLE',
        'REPORT_FINALIZING', 'REPORT_FINALIZED', 'REFERENCE_RECEIPT_EXPIRED', 'REFERENCE_CONTENT_CHANGED',
        'REPORT_MEETING_SKIPPED', 'REPORT_MEETING_OCCUPIED', 'REPORT_MEETING_REVISION_CONFLICT',
    }:
        return 409
    if error.code == 'REFERENCE_INVALID':
        return 422
    if error.code == 'REPORT_LIMIT':
        return 413
    return 400
