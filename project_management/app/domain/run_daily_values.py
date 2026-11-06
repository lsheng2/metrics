import re
import uuid
from typing import Mapping

from project_management.app.domain.run_contracts import DailyRunTarget, RunError
from project_management.app.domain.report_templates import UserTemplateSelection


def daily_template_payload(template):
    validate_daily_template(template)
    return {
        'template_id': _uuid(template.template_id),
        'revision': template.revision,
        'revision_hash': _hash(template.revision_hash),
        'origin': 'user',
    }


def daily_template_from_mapping(value: Mapping):
    if set(value) != {'template_id', 'revision', 'revision_hash', 'origin'}:
        raise RunError('RUN_STORAGE_INVALID')
    if value['origin'] != 'user' or type(value['revision']) is not int or value['revision'] < 1:
        raise RunError('RUN_STORAGE_INVALID')
    return UserTemplateSelection(
        _uuid(value['template_id']),
        value['revision'],
        _hash(value['revision_hash']),
    )


def daily_target_payload(target):
    target = validate_daily_target(target)
    return {
        'kind': 'daily_preparation',
        'preparation_id': target.preparation_id,
        'preparation_intent_hash': target.preparation_intent_hash,
        'draft_id': target.draft_id,
        'effective_selection_hash': target.effective_selection_hash,
        'source_mode': target.source_mode,
        'analysis_mode': target.analysis_mode,
    }


def daily_target_from_mapping(value: Mapping) -> DailyRunTarget:
    if set(value) != {
        'kind',
        'preparation_id',
        'preparation_intent_hash',
        'draft_id',
        'effective_selection_hash',
        'source_mode',
        'analysis_mode',
    }:
        raise RunError('RUN_STORAGE_INVALID')
    if value['kind'] != 'daily_preparation':
        raise RunError('RUN_STORAGE_INVALID')
    return DailyRunTarget(
        _uuid(value['preparation_id']),
        _hash(value['preparation_intent_hash']),
        _uuid(value['draft_id']),
        _hash(value['effective_selection_hash']),
        _literal(value['source_mode'], 'refresh'),
        _analysis_mode(value['analysis_mode']),
    )


def validate_daily_template(template):
    if not isinstance(template, UserTemplateSelection):
        raise RunError('RUN_INVALID')
    _uuid(template.template_id)
    if type(template.revision) is not int or template.revision < 1:
        raise RunError('RUN_INVALID')
    _hash(template.revision_hash)


def validate_daily_target(target):
    if not isinstance(target, DailyRunTarget):
        raise RunError('RUN_INVALID')
    _uuid(target.preparation_id)
    _hash(target.preparation_intent_hash)
    _uuid(target.draft_id)
    _hash(target.effective_selection_hash)
    if target.source_mode != 'refresh' or target.analysis_mode not in {'manual_only', 'changed_items'}:
        raise RunError('RUN_INVALID')
    return target


def _analysis_mode(value):
    if value not in {'manual_only', 'changed_items'}:
        raise RunError('RUN_STORAGE_INVALID')
    return value


def _uuid(value) -> str:
    if type(value) is not str or re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value) is None:
        raise RunError('RUN_INVALID')
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise RunError('RUN_INVALID') from None


def _hash(value) -> str:
    if type(value) is not str or re.fullmatch(r'[a-f0-9]{64}', value) is None:
        raise RunError('RUN_INVALID')
    return value


def _literal(value, expected):
    if value != expected:
        raise RunError('RUN_STORAGE_INVALID')
    return expected
