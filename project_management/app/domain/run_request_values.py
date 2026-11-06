from typing import Mapping

from project_management.app.domain.report_presentation import TemplateSelection
from project_management.app.domain.run_contracts import DailyRunRequest, RunError, RunRequest
from project_management.app.domain.run_daily_values import (
    daily_target_from_mapping,
    daily_target_payload,
    daily_template_from_mapping,
    daily_template_payload,
)


def request_from_mapping(value: Mapping):
    if set(value) == {'command_id', 'expected_stage_hash', 'template', 'timezone'}:
        template = value['template']
        if not isinstance(template, Mapping) or set(template) != {'template_id', 'version', 'options'}:
            raise RunError('RUN_STORAGE_INVALID')
        return RunRequest(
            _uuid(value['command_id']),
            _hash(value['expected_stage_hash']),
            TemplateSelection(_text(template['template_id']), _text(template['version']), _mapping(template['options'])),
            _text(value['timezone'], 128),
        )
    if set(value) != {'schema_version', 'command_id', 'expected_stage_hash', 'template', 'timezone', 'target'}:
        raise RunError('RUN_STORAGE_INVALID')
    if value['schema_version'] != 2 or not isinstance(value['template'], Mapping):
        raise RunError('RUN_STORAGE_INVALID')
    return DailyRunRequest(
        _uuid(value['command_id']),
        _hash(value['expected_stage_hash']),
        daily_template_from_mapping(value['template']),
        _text(value['timezone'], 128),
        daily_target_from_mapping(_mapping(value['target'])),
    )


def request_payload(request):
    if isinstance(request, DailyRunRequest):
        return {
            'schema_version': 2,
            'command_id': request.command_id,
            'expected_stage_hash': request.expected_stage_hash,
            'template': daily_template_payload(request.template),
            'timezone': request.timezone,
            'target': daily_target_payload(request.target),
        }
    return {
        'command_id': request.command_id,
        'expected_stage_hash': request.expected_stage_hash,
        'template': template_payload(request.template),
        'timezone': request.timezone,
    }


def template_payload(template: TemplateSelection):
    return {
        'template_id': template.template_id,
        'version': template.version,
        'options': template.options,
    }


def _uuid(value):
    from project_management.app.domain.run_daily_values import _uuid as validate

    return validate(value)


def _hash(value):
    from project_management.app.domain.run_daily_values import _hash as validate

    return validate(value)


def _text(value, limit=2048):
    if type(value) is not str or not value or len(value) > limit or value != value.strip() or any(ord(char) < 32 for char in value):
        raise RunError('RUN_INVALID')
    return value


def _mapping(value):
    if not isinstance(value, Mapping):
        raise RunError('RUN_STORAGE_INVALID')
    return value
