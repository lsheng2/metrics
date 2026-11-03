from dataclasses import dataclass
from typing import Literal, Mapping
from uuid import UUID, uuid5

from project_management.app.domain.report_draft_values import (
    validate_hash_text,
    validate_time_text,
    validate_uuid_text,
)
from project_management.app.domain.report_contracts import ReportError

PUBLICATION_FILES = ('snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt', 'manifest.json')
MANIFEST_HASHED_FILES = ('snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt')


@dataclass(frozen=True, slots=True)
class PublicationManifest:
    schema_version: Literal[1]
    publication_id: str
    draft_id: str
    draft_revision: int
    draft_revision_hash: str
    purpose: Literal['standup', 'historical_export']
    parent_publication_id: str | None
    baseline_publication_id: str | None
    source_as_of: str
    finalized_at: str
    finalized_by: str
    snapshot_hash: str
    template_hash: str
    file_hashes: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ReportPublication:
    manifest: PublicationManifest
    manifest_sha256: str
    commit_id: str
    checkout_state: str


def publication_id_for(draft_id: str, revision: int, purpose: str) -> str:
    return str(uuid5(UUID(validate_uuid_text(draft_id)), f'{_positive_int(revision)}:{_purpose(purpose)}'))


def publication_path(publication_id: str, name: str) -> str:
    publication_id = validate_uuid_text(publication_id)
    if name not in PUBLICATION_FILES:
        raise ReportError('REPORT_INVALID')
    return f'report_publications/{publication_id}/{name}'


def manifest_from_mapping(value) -> PublicationManifest:
    expected = {
        'schema_version', 'publication_id', 'draft_id', 'draft_revision', 'draft_revision_hash',
        'purpose', 'parent_publication_id', 'baseline_publication_id', 'source_as_of',
        'finalized_at', 'finalized_by', 'snapshot_hash', 'template_hash', 'file_hashes',
    }
    _keys(value, expected)
    return PublicationManifest(
        _literal(value['schema_version'], 1), validate_uuid_text(value['publication_id']),
        validate_uuid_text(value['draft_id']), _positive_int(value['draft_revision']),
        validate_hash_text(value['draft_revision_hash']), _purpose(value['purpose']),
        _optional_uuid(value['parent_publication_id']), _optional_uuid(value['baseline_publication_id']),
        validate_time_text(value['source_as_of']), validate_time_text(value['finalized_at']),
        _str(value['finalized_by']), validate_hash_text(value['snapshot_hash']),
        validate_hash_text(value['template_hash']), _file_hashes(value['file_hashes'], MANIFEST_HASHED_FILES),
    )


def finalization_from_mapping(value):
    expected = {
        'schema_version', 'command_id', 'request_hash', 'publication_id', 'draft_id',
        'draft_revision', 'draft_revision_hash', 'purpose', 'finalized_at', 'finalized_by',
        'snapshot_hash', 'template_hash', 'file_hashes', 'file_sizes',
    }
    _keys(value, expected)
    return {
        'schema_version': _literal(value['schema_version'], 1), 'command_id': validate_uuid_text(value['command_id']),
        'request_hash': validate_hash_text(value['request_hash']), 'publication_id': validate_uuid_text(value['publication_id']),
        'draft_id': validate_uuid_text(value['draft_id']), 'draft_revision': _positive_int(value['draft_revision']),
        'draft_revision_hash': validate_hash_text(value['draft_revision_hash']), 'purpose': _purpose(value['purpose']),
        'finalized_at': validate_time_text(value['finalized_at']), 'finalized_by': _str(value['finalized_by']),
        'snapshot_hash': validate_hash_text(value['snapshot_hash']), 'template_hash': validate_hash_text(value['template_hash']),
        'file_hashes': _file_hashes(value['file_hashes'], PUBLICATION_FILES), 'file_sizes': _file_sizes(value['file_sizes']),
    }


def _file_hashes(value, names):
    if not isinstance(value, Mapping) or set(value.keys()) != set(names):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return {name: validate_hash_text(value[name]) for name in names}


def _file_sizes(value):
    if not isinstance(value, Mapping) or set(value.keys()) != set(PUBLICATION_FILES):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if any(type(size) is not int or size < 0 for size in value.values()):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return dict(value)


def _keys(value, expected):
    if not isinstance(value, Mapping) or set(value.keys()) != expected:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _str(value) -> str:
    if type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _optional_uuid(value):
    return None if value is None else validate_uuid_text(value)


def _positive_int(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _purpose(value):
    if value not in {'standup', 'historical_export'} or type(value) is not str:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _literal(value, expected):
    if value != expected or type(value) is not type(expected):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return expected
