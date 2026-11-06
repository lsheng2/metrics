import json
from uuid import UUID

from project_management.app.api import reports as report_api


MAX_COMPLETION_REQUEST_BYTES = 8192
REQUEST_KEYS = {
    'request_id',
    'token',
    'expected_revision',
    'expected_revision_hash',
    'snapshot_hash',
    'region_target',
    'editor_epoch',
    'local_version',
}


def parse_completion_request(request):
    body = request.body
    if len(body) > MAX_COMPLETION_REQUEST_BYTES:
        raise report_api.ReportError('COMPLETION_REQUEST_TOO_LARGE')
    try:
        payload = json.loads(body.decode('utf-8'), object_pairs_hook=reject_duplicate_json_keys,
                             parse_constant=reject_constant)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST') from None
    if not isinstance(payload, dict) or set(payload) != REQUEST_KEYS:
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return report_api.CompletionRequest(
        request_id=uuid_text(payload['request_id']),
        token=text(payload['token'], 33),
        expected_revision=bounded_int(payload['expected_revision'], 1, 1_000_000),
        expected_revision_hash=hash_text(payload['expected_revision_hash']),
        snapshot_hash=hash_text(payload['snapshot_hash']),
        region_target=mapping(payload['region_target']),
        editor_epoch=text(payload['editor_epoch'], 128),
        local_version=bounded_int(payload['local_version'], 0, 1_000_000),
    )


def reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError('invalid constant')


def uuid_text(value):
    if type(value) is not str:
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST') from None
    if str(parsed) != value.lower():
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return value


def hash_text(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return value


def bounded_int(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return value


def text(value, limit):
    if type(value) is not str or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return value


def mapping(value):
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise report_api.ReportError('COMPLETION_INVALID_REQUEST')
    return value
