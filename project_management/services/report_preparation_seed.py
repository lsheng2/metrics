from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_authoring import authored_edit_from_mapping
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_contracts import ReportError


def validate_prepared_context_seed(seed):
    expected_v1 = {
        'schema_version', 'preparation_id', 'create_command_id', 'draft_id', 'project_id', 'stage_id',
        'owner_subject', 'series_id', 'series_policy_hash', 'effective_selection_hash',
        'template_use_hash', 'expected_baseline_ref', 'meeting_key', 'period_key',
        'stage_hash', 'snapshot_hash', 'context', 'context_hash', 'created_at',
        'template_request_hash', 'series_policy_revision',
    }
    expected_v2 = expected_v1 | {'authority'}
    expected_v3 = expected_v1 | {'preservation'}
    expected_v3_authorized = expected_v2 | {'preservation'}
    if not isinstance(seed, dict):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if seed['schema_version'] == 1 and set(seed) != expected_v1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if seed['schema_version'] == 2 and set(seed) != expected_v2:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if seed['schema_version'] == 3 and set(seed) != expected_v3 and set(seed) != expected_v3_authorized:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if seed['schema_version'] not in {1, 2, 3}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if seed['schema_version'] == 2:
        _authority(seed['authority'], seed)
    if seed['schema_version'] == 3:
        if 'authority' in seed:
            _authority(seed['authority'], seed)
        _preservation(seed['preservation'])
    if seed['context_hash'] != sha256_bytes(canonical_bytes(seed['context'])):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    context = validate_daily_authoring_context(seed['context'], series_id=seed['series_id'])
    if (seed['meeting_key'] != context_meeting_key(context)
            or seed['period_key'] != context_period_key(context)
            or context['series_policy_hash'] != seed['series_policy_hash']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return context


def _preservation(value):
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    common = {'schema_version', 'source_kind', 'initial_authored_edits', 'initial_authored_edits_hash', 'review_issues', 'preservation_hash'}
    if value.get('source_kind') == 'parent_draft_revision':
        expected = common | {'parent_draft_id', 'parent_draft_revision', 'parent_draft_revision_hash'}
    elif value.get('source_kind') == 'source_publication':
        expected = common | {'publication_id', 'manifest_hash', 'commit'}
    else:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    edits = tuple(authored_edit_from_mapping(item) for item in value['initial_authored_edits'])
    if value['initial_authored_edits_hash'] != sha256_bytes(canonical_bytes(edits)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    tuple(_review_issue(item) for item in value['review_issues'])
    payload = {key: item for key, item in value.items() if key not in {'initial_authored_edits', 'preservation_hash'}}
    if value['preservation_hash'] != sha256_bytes(canonical_bytes(payload)):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _review_issue(value):
    if not isinstance(value, dict) or set(value) != {'code', 'target', 'reason'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if type(value['code']) is not str or type(value['reason']) is not str or not isinstance(value['target'], dict):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _authority(value, seed):
    expected = {
        'schema_version', 'kind', 'preparation_id', 'preparation_intent_hash',
        'slot_id', 'slot_key', 'draft_id', 'create_command_id', 'series_id', 'meeting_date',
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if (value['schema_version'] != 1
            or value['kind'] != 'daily_preparation_active_slot'
            or value['preparation_id'] != seed['preparation_id']
            or value['draft_id'] != seed['draft_id']
            or value['create_command_id'] != seed['create_command_id']
            or value['series_id'] != seed['series_id']):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['slot_key'] != {'series_id': value['series_id'], 'local_date': value['meeting_date']}:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def context_meeting_key(context):
    meeting = context['meeting']
    return f"{meeting['calendar_id']}:{meeting['calendar_revision']}:{meeting['local_date']}"


def context_period_key(context):
    period = context['period']
    return f"{period['calendar_id']}:{period['calendar_revision']}:{period['workweek_year']}:ww{period['workweek']}"
