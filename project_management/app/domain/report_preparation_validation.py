from typing import Mapping

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import (
    canonical_hash,
    validate_date_text,
    validate_git_commit_text,
    validate_hash_text,
    validate_uuid_text,
)


def preparation_binding_hash(intent: Mapping) -> str:
    # Validated intents distinguish draft content authority from the full slot hash.
    return (intent.get('preparation_intent_hash') or intent.get('reprepare_intent_hash')
            or canonical_hash(intent))


def validate_template_selection_payload(value):
    _keys(value, {'template_id', 'revision', 'revision_hash', 'origin'})
    revision = value['revision']
    if type(revision) is not int or revision < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['origin'] != 'user':
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {
        'template_id': validate_uuid_text(value['template_id']),
        'revision': revision,
        'revision_hash': validate_hash_text(value['revision_hash']),
        'origin': 'user',
    }


def validate_publication_ref_payload(value):
    if value is None:
        return None
    _keys(value, {'publication_id', 'manifest_hash', 'commit'})
    return {
        'publication_id': validate_uuid_text(value['publication_id']),
        'manifest_hash': validate_hash_text(value['manifest_hash']),
        'commit': validate_git_commit_text(value['commit']),
    }


def validate_gap_ids(value):
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    result = tuple(validate_uuid_text(item) for item in value)
    if len(set(result)) != len(result):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return result


def validate_effective_selection_payload(value):
    expected = {
        'series_id', 'series_policy_hash', 'meeting_date', 'meeting_key',
        'period_key', 'calendar_id', 'calendar_revision', 'timezone',
        'expected_baseline_ref', 'template_selection', 'source_mode',
        'capture_id', 'analysis_mode', 'acknowledge_gap_draft_ids',
    }
    _keys(value, expected)
    if value['source_mode'] not in {'saved_capture', 'refresh'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['analysis_mode'] not in {'manual_only', 'changed_items'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'saved_capture' and value['analysis_mode'] != 'manual_only':
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if value['source_mode'] == 'refresh' and value['analysis_mode'] not in {'manual_only', 'changed_items'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if type(value['calendar_id']) is not str or not value['calendar_id']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if type(value['calendar_revision']) is not int or value['calendar_revision'] < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if type(value['timezone']) is not str or not value['timezone']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {
        'series_id': validate_uuid_text(value['series_id']),
        'series_policy_hash': validate_hash_text(value['series_policy_hash']),
        'meeting_date': validate_date_text(value['meeting_date']),
        'meeting_key': _text(value['meeting_key']),
        'period_key': _text(value['period_key']),
        'calendar_id': value['calendar_id'],
        'calendar_revision': value['calendar_revision'],
        'timezone': value['timezone'],
        'expected_baseline_ref': validate_publication_ref_payload(value['expected_baseline_ref']),
        'template_selection': validate_template_selection_payload(value['template_selection']),
        'source_mode': value['source_mode'],
        'capture_id': validate_uuid_text(value['capture_id']),
        'analysis_mode': value['analysis_mode'],
        'acknowledge_gap_draft_ids': validate_gap_ids(value['acknowledge_gap_draft_ids']),
    }


def validate_intent_nested_payload(value):
    template = validate_template_selection_payload(value['template_selection'])
    baseline = validate_publication_ref_payload(value['expected_baseline_ref'])
    gaps = validate_gap_ids(value['acknowledge_gap_draft_ids'])
    effective = validate_effective_selection_payload(value['effective_selection'])
    original = request_payload_from_intent(value) if value.get('schema_version') == 2 else None
    expected = {
        'series_id': value['series_id'],
        'series_policy_hash': value['series_policy_hash'],
        'meeting_date': value['meeting_date'],
        'meeting_key': value['meeting_key'],
        'period_key': value['period_key'],
        'expected_baseline_ref': baseline,
        'template_selection': template,
        'source_mode': value['source_mode'],
        'capture_id': value['capture_id'],
        'analysis_mode': value['analysis_mode'],
        'acknowledge_gap_draft_ids': gaps,
        'timezone': value['timezone'],
    }
    for key, expected_value in expected.items():
        if effective[key] != expected_value:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    _verify_calendar_fields(effective)
    if original is not None:
        _verify_original_request_binding(original, effective, template, baseline, gaps)
    return template, baseline, gaps, effective


def request_payload_from_intent(value):
    if value.get('schema_version') == 2:
        request = value.get('original_request')
        _keys(request, {
            'series_id', 'meeting_date', 'expected_series_policy_hash',
            'expected_baseline_ref', 'template_selection', 'source_mode',
            'capture_id', 'analysis_mode', 'acknowledge_gap_draft_ids',
        })
        if request['source_mode'] != 'refresh' or request['capture_id'] is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if request['analysis_mode'] not in {'manual_only', 'changed_items'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return {
            'series_id': validate_uuid_text(request['series_id']),
            'meeting_date': validate_date_text(request['meeting_date']),
            'expected_series_policy_hash': validate_hash_text(request['expected_series_policy_hash']),
            'expected_baseline_ref': validate_publication_ref_payload(request['expected_baseline_ref']),
            'template_selection': validate_template_selection_payload(request['template_selection']),
            'source_mode': 'refresh',
            'capture_id': None,
            'analysis_mode': request['analysis_mode'],
            'acknowledge_gap_draft_ids': validate_gap_ids(request['acknowledge_gap_draft_ids']),
        }
    if value.get('schema_version') == 3:
        template, baseline, gaps, _ = validate_intent_nested_payload(value)
        return {
            'kind': 'daily_reprepare',
            'command_id': value['command_id'],
            'parent_preparation_id': value['parent_preparation_id'],
            'parent_intent_hash': value['parent_intent_hash'],
            'parent_operation_id': value['parent_operation_id'],
            'expected_parent_operation_revision': value['expected_parent_operation_revision'],
            'expected_parent_operation_state': value['expected_parent_operation_state'],
            'parent_draft_id': value['parent_draft_id'],
            'expected_parent_draft_revision': value['expected_parent_draft_revision'],
            'expected_parent_draft_revision_hash': value['expected_parent_draft_revision_hash'],
            'series_id': value['series_id'],
            'meeting_date': value['meeting_date'],
            'expected_series_policy_hash': value['series_policy_hash'],
            'expected_baseline_ref': baseline,
            'template_selection': template,
            'source_mode': value['source_mode'],
            'capture_id': None if value['source_mode'] == 'refresh' else value['capture_id'],
            'analysis_mode': value['analysis_mode'],
            'acknowledge_gap_draft_ids': gaps,
        }
    template, baseline, gaps, _ = validate_intent_nested_payload(value)
    return {
        'series_id': value['series_id'],
        'meeting_date': value['meeting_date'],
        'expected_series_policy_hash': value['series_policy_hash'],
        'expected_baseline_ref': baseline,
        'template_selection': template,
        'source_mode': value['source_mode'],
        'capture_id': value['capture_id'],
        'analysis_mode': value['analysis_mode'],
        'acknowledge_gap_draft_ids': gaps,
    }


def _verify_calendar_fields(effective):
    parts = effective['meeting_key'].split(':')
    if len(parts) != 3:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    try:
        revision = int(parts[1])
    except ValueError:
        raise ReportError('REPORT_ARTIFACT_INVALID') from None
    if (parts[0] != effective['calendar_id']
            or revision != effective['calendar_revision']
            or parts[2] != effective['meeting_date']):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _verify_original_request_binding(original, effective, template, baseline, gaps):
    expected = {
        'series_id': effective['series_id'],
        'meeting_date': effective['meeting_date'],
        'expected_series_policy_hash': effective['series_policy_hash'],
        'expected_baseline_ref': baseline,
        'template_selection': template,
        'source_mode': effective['source_mode'],
        'capture_id': None,
        'analysis_mode': effective['analysis_mode'],
        'acknowledge_gap_draft_ids': gaps,
    }
    if original != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _keys(value, expected):
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _text(value):
    if type(value) is not str or not value:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value
