from dataclasses import asdict
import json
from uuid import uuid4

from django.http import JsonResponse, QueryDict
from django.utils.translation import gettext as _

from project_management.app.api import reports as report_api
from ui_web.project_access import private_no_store
from ui_web.report_authoring_forms import reject_duplicate_json_keys
from ui_web.report_authoring_responses import report_status


def daily_request_data(request):
    if len(request.body) > 65536:
        raise report_api.ReportError('REPORT_LIMIT')
    if request.content_type != 'application/json':
        return request.POST
    try:
        payload = json.loads(request.body, object_pairs_hook=reject_duplicate_json_keys)
        if not isinstance(payload, dict):
            raise ValueError
        data = QueryDict('', mutable=True)
        for key, value in payload.items():
            values = value if key == 'acknowledge_gap_draft_ids' and isinstance(value, list) else [value]
            if any(item is not None and type(item) not in {str, int, bool} for item in values):
                raise ValueError
            data.setlist(key, ['' if item is None else str(item) for item in values])
        return data
    except (ValueError, TypeError, UnicodeError):
        raise report_api.ReportError('REPORT_INVALID') from None


def daily_status(error):
    if error.code in {'REPORT_BASELINE_PENDING', 'REPORT_BASELINE_CONFLICT',
                      'REPORT_PREPARATION_COMMAND_CONFLICT', 'RUN_BUSY', 'RUN_REVISION_CONFLICT'}:
        return 409
    if error.code in {'RUN_UNAVAILABLE', 'REPORT_AI_UNAVAILABLE',
                      'REPORT_HISTORY_UNAVAILABLE', 'REPORT_CALENDAR_UNAVAILABLE'}:
        return 503
    if error.code in {'RUN_NOT_FOUND', 'REPORT_NOT_FOUND'}:
        return 404
    return report_status(error)


def daily_error_message(error):
    return {
        'REPORT_BASELINE_PENDING': _('Earlier saved drafts need finalization or explicit gap confirmation.'),
        'REPORT_BASELINE_CONFLICT': _('The daily baseline changed. Preview it again before generating.'),
        'REPORT_REVISION_CONFLICT': _('The selected revision changed. Preview the current version.'),
        'REPORT_PREPARATION_COMMAND_CONFLICT': _('This command was already used with different choices.'),
        'REPORT_HISTORY_UNAVAILABLE': _('Report history requires review. The original draft is preserved.'),
        'REPORT_CALENDAR_UNAVAILABLE': _('The selected reporting calendar is unavailable.'),
        'RUN_UNAVAILABLE': _('Refresh runtime is unavailable. Saved-capture manual preparation is still available.'),
        'REPORT_AI_UNAVAILABLE': _('AI analysis is unavailable. Manual preparation is still available.'),
        'REPORT_INVALID': _('Report request is invalid.'),
        'REPORT_NOT_FOUND': _('Report is not available.'),
        'REPORT_LIMIT': _('Report is over the configured limit.'),
    }.get(error.code, _('Report request failed.'))


def daily_json(*, result=None, error=None, status=200, request_id=None):
    value = asdict(result) if result is not None and hasattr(result, '__dataclass_fields__') else result
    problem = None if error is None else {
        'code': error.code,
        'message': error.message,
        'retryable': status in {429, 503, 504},
        'details': {},
    }
    return private_no_store(JsonResponse({
        'schema_version': 1,
        'request_id': request_id or str(uuid4()),
        'result': value,
        'error': problem,
    }, status=status))
