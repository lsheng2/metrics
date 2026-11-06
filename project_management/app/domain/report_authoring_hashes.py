from dataclasses import asdict

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_templates import PinnedTemplateUse


def authored_create_template_use_request_hash(selection, template, preparation_id):
    return _hash({
        'selection': selection,
        'template': template,
        'preparation_id': validate_uuid_text(preparation_id),
    })


def authored_create_request_hash(selection, template, preparation_id=None, context_hash=None, preservation_hash=None):
    if preparation_id is None:
        if context_hash is not None or preservation_hash is not None:
            raise ReportError('REPORT_INVALID')
        return _hash({'selection': selection, 'template': template, 'preparation_id': None})
    payload = {
        'selection': selection,
        'template': template,
        'preparation_id': validate_uuid_text(preparation_id),
        'context_hash': validate_hash_text(context_hash),
    }
    if preservation_hash is not None:
        payload['preservation_hash'] = validate_hash_text(preservation_hash)
    return _hash(payload)


def pinned_template_use_payload(pinned):
    if not isinstance(pinned, PinnedTemplateUse):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {
        'command_id': validate_uuid_text(pinned.command_id),
        'draft_id': validate_uuid_text(pinned.draft_id),
        'request_hash': validate_hash_text(pinned.request_hash),
        'template_snapshot': pinned.template_snapshot,
        'template_definition': asdict(pinned.template_definition),
    }


def pinned_template_use_hash(pinned):
    return _hash(pinned_template_use_payload(pinned))


def _hash(value):
    try:
        return sha256_bytes(canonical_bytes(value))
    except ArchiveError:
        raise ReportError('REPORT_INVALID') from None
