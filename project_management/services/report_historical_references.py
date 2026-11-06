from typing import Mapping

from project_management.app.domain.report_draft_values import canonical_hash
from project_management.app.domain.report_draft_values import validate_git_commit_text, validate_hash_text, validate_uuid_text
from project_management.app.domain.capture_values import decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring import authored_edit_from_mapping
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_publication_contracts import publication_path
from project_management.services.report_publication_reads import ReportPublicationReader


RECORD_V2_KEYS = {
    'schema_version', 'reference_id', 'option_id', 'issued_fragment_hash',
    'content_basis', 'observation', 'historical_association',
}
ASSOCIATION_COMMON_KEYS = {'schema_version', 'kind', 'target_hash', 'reference_id', 'record_hash'}
ASSOCIATION_KEYS = {
    'parent_draft_revision': ASSOCIATION_COMMON_KEYS | {
        'parent_draft_id', 'parent_draft_revision', 'parent_draft_revision_hash',
    },
    'source_publication': ASSOCIATION_COMMON_KEYS | {'publication_id', 'manifest_hash', 'commit'},
}


class HistoricalReferenceResolver:
    def __init__(self, draft_service, actor, project_id, stage_id):
        self.draft_service = draft_service
        self.actor = actor
        self.project_id = project_id
        self.stage_id = stage_id

    def __call__(self, record):
        association = _historical_association(record)
        if association['kind'] == 'source_publication':
            return self._resolve_publication(association)
        if association['kind'] != 'parent_draft_revision':
            raise ReportError('REFERENCE_INVALID')
        with self.draft_service.archive._report_repository(
            self.actor, self.project_id, self.stage_id, write=False,
        ) as repository:
            try:
                parent = self.draft_service._store(repository).read_draft(
                    association['parent_draft_id'],
                    revision=association['parent_draft_revision'],
                )
            except ArchiveError:
                raise ReportError('REFERENCE_INVALID') from None
        if parent.revision_hash != association['parent_draft_revision_hash']:
            return False
        for edit in parent.authored_edits:
            if canonical_hash(edit.target) != association['target_hash']:
                continue
            if any(_matches_parent_record(parent_record, association) for parent_record in tuple(edit.reference_observations or ())):
                return True
        return False

    def _resolve_publication(self, association):
        with self.draft_service.archive._report_repository(
            self.actor, self.project_id, self.stage_id, write=False,
        ) as repository:
            publication = ReportPublicationReader(repository).get(association['publication_id'], self.actor.subject)
            if publication.manifest_sha256 != association['manifest_hash'] or publication.commit_id != association['commit']:
                return False
            edits = decode_json(repository.read_file(publication_path(publication.manifest.publication_id, 'edits.json'), publication.commit_id))
        for edit in _selected_authored_edits(edits):
            if canonical_hash(edit.target) != association['target_hash']:
                continue
            if any(_matches_parent_record(parent_record, association) for parent_record in tuple(edit.reference_observations or ())):
                return True
        return False


def _matches_parent_record(parent_record, association):
    legacy = _legacy_reference_record(parent_record)
    return (
        legacy.get('reference_id') == association['reference_id']
        and canonical_hash(legacy) == association['record_hash']
    )


def _legacy_reference_record(record):
    if isinstance(record, dict) and record.get('schema_version') == 2:
        return _validated_legacy_record(record)
    return record


def _historical_association(record):
    legacy = _validated_legacy_record(record)
    association = record['historical_association']
    _validate_association(association, legacy)
    return association


def _validated_legacy_record(record):
    _keys(record, RECORD_V2_KEYS)
    _version(record['schema_version'], 2)
    _uuid(record['reference_id'])
    _hash(record['issued_fragment_hash'])
    option_id = record['option_id']
    if not isinstance(option_id, str) or option_id not in {'id', 'id_title', 'id_title_owner'}:
        raise ReportError('REFERENCE_INVALID')
    if record['content_basis'] != 'human_composed':
        raise ReportError('REFERENCE_INVALID')
    if not isinstance(record['observation'], Mapping):
        raise ReportError('REFERENCE_INVALID')
    return {key: record[key] for key in (
        'reference_id', 'option_id', 'issued_fragment_hash', 'content_basis', 'observation',
    )}


def _validate_association(association, legacy):
    if not isinstance(association, Mapping):
        raise ReportError('REFERENCE_INVALID')
    kind = association.get('kind')
    if not isinstance(kind, str) or kind not in ASSOCIATION_KEYS:
        raise ReportError('REFERENCE_INVALID')
    _keys(association, ASSOCIATION_KEYS[kind])
    _version(association['schema_version'], 1)
    _hash(association['target_hash'])
    _uuid(association['reference_id'])
    _hash(association['record_hash'])
    if association['reference_id'] != legacy['reference_id'] or association['record_hash'] != canonical_hash(legacy):
        raise ReportError('REFERENCE_INVALID')
    if kind == 'parent_draft_revision':
        _uuid(association['parent_draft_id'])
        _positive_int(association['parent_draft_revision'])
        _hash(association['parent_draft_revision_hash'])
        return
    _uuid(association['publication_id'])
    _hash(association['manifest_hash'])
    _commit(association['commit'])


def _keys(value, expected):
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReportError('REFERENCE_INVALID')


def _version(value, expected):
    if type(value) is not int or value != expected:
        raise ReportError('REFERENCE_INVALID')


def _positive_int(value):
    if type(value) is not int or value < 1:
        raise ReportError('REFERENCE_INVALID')


def _uuid(value):
    try:
        return validate_uuid_text(value)
    except ReportError:
        raise ReportError('REFERENCE_INVALID') from None


def _hash(value):
    try:
        return validate_hash_text(value)
    except ReportError:
        raise ReportError('REFERENCE_INVALID') from None


def _commit(value):
    try:
        return validate_git_commit_text(value)
    except ReportError:
        raise ReportError('REFERENCE_INVALID') from None


def _selected_authored_edits(edits):
    selected_revision = edits.get('selected_revision')
    if type(selected_revision) is not int or type(edits.get('revisions')) is not list:
        raise ReportError('REFERENCE_INVALID')
    for item in edits['revisions']:
        if not isinstance(item, dict) or item.get('revision') != selected_revision:
            continue
        payload = item.get('payload')
        if not isinstance(payload, dict) or not isinstance(payload.get('edits'), list):
            raise ReportError('REFERENCE_INVALID')
        return tuple(authored_edit_from_mapping(edit) for edit in payload['edits'])
    raise ReportError('REFERENCE_INVALID')
