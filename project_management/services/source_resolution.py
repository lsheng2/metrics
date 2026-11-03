import hashlib
import re

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.capture_validation import text
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.source_resolution import (
    SourceDependencyDefinition, SourceResolutionInput, SourceResolutionRef,
)
from project_management.storage.admission import admit, finalize_growth


RESOLUTION_PATH = 'source_resolution/first.json'


def validate_resolution(definition, stage):
    if not isinstance(definition, SourceResolutionInput):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    if (definition.original_rule_hash != stage.definition_hash
            or definition.provider_id != stage.descriptor.provider_id
            or definition.effective_query != stage.descriptor.query):
        raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
    for name in ('endpoint_id', 'principal_id', 'resolver_revision'):
        text(getattr(definition, name))
    if not isinstance(definition.dependencies, tuple) or len(definition.dependencies) > 128:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    keys = []
    for dependency in definition.dependencies:
        if (not isinstance(dependency, SourceDependencyDefinition)
                or not isinstance(dependency.filter_id, str)
                or not re.fullmatch('[1-9][0-9]{0,63}', dependency.filter_id)
                or not isinstance(dependency.query, str) or not dependency.query or len(dependency.query) > 16384
                or hashlib.sha256(dependency.query.encode('utf-8')).hexdigest() != dependency.source_hash):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        keys.append(dependency.filter_id)
    if sorted(set(keys)) != keys:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    canonical_bytes(definition)


def resolution_from_record(record, stage):
    try:
        if set(record) != {'schema_version', 'definition', 'resolution_hash'} or type(record['schema_version']) is not int or record['schema_version'] != 1:
            raise ValueError
        value = dict(record['definition'])
        value['dependencies'] = tuple(SourceDependencyDefinition(**row) for row in value['dependencies'])
        definition = SourceResolutionInput(**value)
        validate_resolution(definition, stage)
        if content_hash(definition) != record['resolution_hash']:
            raise ValueError
        return definition
    except (KeyError, ValueError, TypeError, UnicodeError):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None


class SourceResolutionArchive:
    def read_source_resolution(self, actor, project_id, stage_id):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        repository = self.repository_factory.open(self.config, project, stage, actor.subject)
        if not repository.stage_root.exists():
            return None
        repository.verify_identity()
        return self._resolution_at_head(repository, stage)

    def bind_source_resolution(self, actor, project_id, stage_id, definition):
        project, stage = self._stage_for_write(actor, project_id, stage_id)
        validate_resolution(definition, stage)
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.initialize()
            existing = self._resolution_at_head(repository, stage)
            if existing is not None:
                if existing != definition:
                    raise ProjectError('SOURCE_CHANGED')
                return SourceResolutionRef(content_hash(existing), repository.commit_for_path(RESOLUTION_PATH))
            if (repository.runtime / 'active-capture.json').exists():
                raise ArchiveError('ARCHIVE_BUSY')
            payload = canonical_bytes({'schema_version': 1, 'definition': definition,
                                       'resolution_hash': content_hash(definition)})
            admit(self.config.root, repository.stage_root, repository.runtime / 'source_resolution',
                  self.config.limits, finalize_growth(1, len(payload)))
            receipt = repository.append_record(
                'first', 'source_resolution', {RESOLUTION_PATH: payload}, expected_head=repository.head(),
                record_fingerprint=content_hash(definition),
            )
            return SourceResolutionRef(content_hash(definition), receipt.commit_id)

    def _resolution_at_head(self, repository, stage):
        if RESOLUTION_PATH not in repository.list_files('source_resolution'):
            return None
        return resolution_from_record(decode_json(repository.read_file(RESOLUTION_PATH)), stage)
