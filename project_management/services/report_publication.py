from dataclasses import replace

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import bytes_hash, canonical_hash
from project_management.app.domain.report_publication_contracts import (
    MANIFEST_HASHED_FILES,
    PUBLICATION_FILES,
    PublicationManifest,
    publication_id_for,
    publication_path,
)
from project_management.services.report_publication_reads import ReportPublicationReader


class ReportPublicationMixin:
    def finalize_and_commit(self, actor, project_id, stage_id, draft_id, *, command_id, expected_revision):
        draft_id = self._uuid(draft_id)
        command_id = self._uuid(command_id)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ReportError('REPORT_INVALID')
        try:
            existing = self._publication_packet(actor, project_id, stage_id, draft_id, command_id, expected_revision)
            if existing is not None:
                return self._resume_packet(actor, project_id, stage_id, draft_id, command_id)
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                draft = store.read_draft(draft_id)
                if draft.state != 'draft':
                    raise ReportError('REPORT_FINALIZED' if draft.state == 'finalized' else 'REPORT_FINALIZING')
                if draft.revision != expected_revision:
                    raise ReportError('REPORT_REVISION_CONFLICT')
                request_hash = self._finalize_request_hash(draft, command_id, expected_revision)
            rendered = self._render_final(draft)
            source_binding = self._current_source_binding(actor, project_id, stage_id, draft)
            finalized_at = self._now()
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                current = store.read_draft(draft_id)
                if (current.revision != expected_revision or current.revision_hash != draft.revision_hash
                        or current.state != 'draft'):
                    raise ReportError('REPORT_REVISION_CONFLICT')
                self._verify_source_binding(repository, actor, project_id, stage_id, current, source_binding)
                self._verify_rendered(current, rendered)
                history = store.revision_history(draft_id, expected_revision)
                files, payload = self._publication_files(actor, current, command_id, request_hash, rendered,
                                                         finalized_at, history)
                store.admit_new_finalization(draft_id, files, payload)
                store.write_finalization_files(draft_id, payload['publication_id'], files)
                store.write_finalization_intent(draft_id, payload)
                return self._append_packet(repository, payload, files)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def resume_finalization(self, actor, project_id, stage_id, draft_id, *, command_id):
        draft_id = self._uuid(draft_id)
        command_id = self._uuid(command_id)
        try:
            return self._resume_packet(actor, project_id, stage_id, draft_id, command_id)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def get_publication(self, actor, project_id, stage_id, publication_id):
        publication_id = self._uuid(publication_id)
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
                return ReportPublicationReader(repository).get(publication_id, actor.subject)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def read_artifact(self, actor, project_id, stage_id, publication_id, format):
        publication_id = self._uuid(publication_id)
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
                return ReportPublicationReader(repository).read_public_artifact(publication_id, format, actor.subject)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def publication_revision_selection(self, actor, project_id, stage_id, publication_id):
        publication_id = self._uuid(publication_id)
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
                publication, snapshot = ReportPublicationReader(repository).snapshot(publication_id)
                if publication.manifest.purpose != 'standup':
                    raise ReportError('REPORT_COMPARISON_UNAVAILABLE')
                return snapshot, publication.manifest
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def _publication_packet(self, actor, project_id, stage_id, draft_id, command_id, expected_revision):
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                if not store.finalization_intent_exists(draft_id):
                    return None
                payload, files = store.finalization_packet(draft_id)
                draft = store.read_draft(draft_id, revision=payload['draft_revision'])
                self._verify_packet_request(draft, payload, command_id, expected_revision, actor.subject)
                return payload, files
        except ArchiveError as error:
            raise ReportError('REPORT_ARTIFACT_INVALID') from error

    def _resume_packet(self, actor, project_id, stage_id, draft_id, command_id):
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            store = self._store(repository)
            payload, files = store.finalization_packet(draft_id)
            draft = store.read_draft(draft_id, revision=payload['draft_revision'])
            self._verify_packet_request(draft, payload, command_id, payload['draft_revision'], actor.subject)
            committed = self._committed_reader(repository, payload)
            if committed is not None:
                return committed
        source_binding = self._current_source_binding(actor, project_id, stage_id, draft)
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            store = self._store(repository)
            payload, files = store.finalization_packet(draft_id)
            current = store.read_draft(draft_id)
            self._verify_packet_request(current, payload, command_id, payload['draft_revision'], actor.subject)
            self._verify_source_binding(repository, actor, project_id, stage_id, draft, source_binding)
            store.admit_finalization_commit(draft_id, files)
            return self._append_packet(repository, payload, files)

    def _append_packet(self, repository, payload, files):
        committed = self._committed_reader(repository, payload)
        if committed is not None:
            return committed
        head = repository.head()
        repository.append_record(
            payload['publication_id'],
            'report_publications',
            {publication_path(payload['publication_id'], name): files[name] for name in PUBLICATION_FILES},
            expected_head=head,
            record_fingerprint=canonical_hash({'publication_id': payload['publication_id'], 'file_hashes': payload['file_hashes']}),
        )
        return ReportPublicationReader(repository).get(payload['publication_id'])

    def _committed_reader(self, repository, payload):
        try:
            commit = repository.find_commit_for_path(publication_path(payload['publication_id'], 'manifest.json'))
        except ReportError as error:
            raise ReportError('REPORT_ARTIFACT_INVALID') from error
        if commit is None:
            return None
        publication = ReportPublicationReader(repository).get(payload['publication_id'], payload['finalized_by'])
        self._verify_committed_payload(publication, payload)
        return publication

    def _render_final(self, draft):
        if self.renderer.template_definition(draft.template) != draft.template_definition:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        rendered = self.renderer.render(
            draft.snapshot, draft.template, draft.edits, draft_id=draft.draft_id,
            revision=draft.revision, revision_hash=draft.revision_hash, edition_state='final',
        )
        self._verify_rendered(draft, rendered)
        return rendered

    def _verify_rendered(self, draft, rendered) -> None:
        if (
            rendered.draft_id != draft.draft_id or rendered.revision != draft.revision
            or rendered.revision_hash != draft.revision_hash or rendered.snapshot_hash != draft.snapshot_hash
            or rendered.template_hash != draft.template_definition.template_hash
        ):
            raise ReportError('REPORT_ARTIFACT_INVALID')

    def _current_source_binding(self, actor, project_id, stage_id, draft):
        if draft.selection.purpose == 'historical_export':
            return None
        selection = replace(draft.selection, parent_publication_id=None)
        current = self.source_reader.read(actor, project_id, stage_id, selection)
        if canonical_bytes(replace(draft.snapshot, source_commit=current.source_commit)) != canonical_bytes(current):
            raise ReportError('REPORT_SOURCE_CHANGED')
        return {'head': current.source_commit, 'selection': selection, 'semantic': self._source_semantic_hash(current)}

    def _verify_source_binding(self, repository, actor, project_id, stage_id, draft, binding) -> None:
        if binding is None:
            return
        current_head = repository.head()
        if current_head == binding['head']:
            return
        if not hasattr(self.source_reader, 'read_from_repository'):
            raise ReportError('REPORT_SOURCE_CHANGED')
        current = self.source_reader.read_from_repository(actor, repository.project, repository.stage,
                                                          repository, binding['selection'], current_head)
        if self._source_semantic_hash(current) != binding['semantic']:
            raise ReportError('REPORT_SOURCE_CHANGED')

    def _source_semantic_hash(self, snapshot):
        return bytes_hash(canonical_bytes(replace(snapshot, source_commit='0' * 40)))

    def _publication_files(self, actor, draft, command_id, request_hash, rendered, finalized_at, history):
        publication_id = publication_id_for(draft.draft_id, draft.revision, draft.selection.purpose)
        snapshot = canonical_bytes(draft.snapshot)
        template = canonical_bytes({'selection': draft.template, 'definition': draft.template_definition})
        edits = canonical_bytes(self._edit_history(draft, history))
        files = {
            'snapshot.json': snapshot,
            'template.json': template,
            'edits.json': edits,
            'report.html': rendered.html_document,
            'report.txt': rendered.plain_text.encode('utf-8'),
        }
        file_hashes = {name: bytes_hash(data) for name, data in files.items()}
        manifest = PublicationManifest(
            1, publication_id, draft.draft_id, draft.revision, draft.revision_hash,
            draft.selection.purpose, draft.parent_publication_id, draft.selection.baseline_publication_id,
            draft.snapshot.source_as_of, finalized_at, actor.subject, draft.snapshot_hash,
            draft.template_definition.template_hash, {name: file_hashes[name] for name in MANIFEST_HASHED_FILES},
        )
        files['manifest.json'] = canonical_bytes(manifest)
        file_hashes['manifest.json'] = bytes_hash(files['manifest.json'])
        payload = {
            'schema_version': 1, 'command_id': command_id, 'request_hash': request_hash,
            'publication_id': publication_id, 'draft_id': draft.draft_id, 'draft_revision': draft.revision,
            'draft_revision_hash': draft.revision_hash, 'purpose': draft.selection.purpose,
            'finalized_at': finalized_at, 'finalized_by': actor.subject, 'snapshot_hash': draft.snapshot_hash,
            'template_hash': draft.template_definition.template_hash, 'file_hashes': file_hashes,
            'file_sizes': {name: len(data) for name, data in files.items()},
        }
        return files, payload

    def _edit_history(self, draft, history):
        return {'schema_version': 1, 'draft_id': draft.draft_id, 'selected_revision': draft.revision,
                'selected_revision_hash': draft.revision_hash, 'revisions': history}

    def _finalize_request_hash(self, draft, command_id, expected_revision):
        return canonical_hash({'command_id': command_id, 'draft_id': draft.draft_id,
                               'expected_revision': expected_revision, 'revision_hash': draft.revision_hash,
                               'purpose': draft.selection.purpose})

    def _packet_request_hash(self, payload, command_id, expected_revision):
        return canonical_hash({'command_id': command_id, 'draft_id': payload['draft_id'],
                               'expected_revision': expected_revision, 'revision_hash': payload['draft_revision_hash'],
                               'purpose': payload['purpose']})

    def _verify_packet_request(self, draft, payload, command_id, expected_revision, actor_subject):
        if payload['command_id'] != command_id or payload['finalized_by'] != actor_subject:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if (payload['draft_id'] != draft.draft_id or payload['draft_revision'] != draft.revision
                or payload['draft_revision_hash'] != draft.revision_hash
                or payload['snapshot_hash'] != draft.snapshot_hash
                or payload['template_hash'] != draft.template_definition.template_hash
                or payload['purpose'] != draft.selection.purpose
                or payload['publication_id'] != publication_id_for(draft.draft_id, draft.revision, draft.selection.purpose)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if payload['request_hash'] != self._finalize_request_hash(draft, command_id, expected_revision):
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _verify_committed_payload(self, publication, payload):
        manifest = publication.manifest
        if (manifest.publication_id != payload['publication_id'] or manifest.draft_id != payload['draft_id']
                or manifest.draft_revision != payload['draft_revision']
                or manifest.draft_revision_hash != payload['draft_revision_hash']
                or manifest.purpose != payload['purpose'] or manifest.finalized_at != payload['finalized_at']
                or manifest.finalized_by != payload['finalized_by'] or manifest.snapshot_hash != payload['snapshot_hash']
                or manifest.template_hash != payload['template_hash']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        for name in MANIFEST_HASHED_FILES:
            if manifest.file_hashes[name] != payload['file_hashes'][name]:
                raise ReportError('REPORT_ARTIFACT_INVALID')
