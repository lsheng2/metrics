from dataclasses import replace
from datetime import UTC, datetime

from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_authoring import AUTHORING_SCHEMA
from project_management.app.domain.report_draft_values import (
    ReportFinalizationStatus,
    ReportArchiveTarget,
    ReportDraftLimits,
    bytes_hash,
    canonical_hash,
    read_json,
    snapshot_from_mapping,
    validate_uuid_text,
)
from project_management.app.domain.report_edits import validate_edit_targets
from project_management.app.domain.report_presentation import ReportEdit, TemplateSelection
from project_management.services.report_draft_listing import ReportDraftListingMixin
from project_management.services.report_authoring_drafts import ReportAuthoringDraftMixin
from project_management.storage.report_drafts import ReportDraftStore
from project_management.services.report_publication import ReportPublicationMixin
from project_management.services.report_prepared_context_reader import PreparedContextReader
from project_management.services.report_templates import ReportTemplateService
from project_management.services.report_draft_rendering import is_pinned_document, render_edits
from project_management.services.report_linked_revision_drafts import ReportLinkedRevisionDraftMixin
from project_management.services.report_period_view_drafts import ReportPeriodViewDraftMixin


class ReportDraftService(ReportLinkedRevisionDraftMixin, ReportPeriodViewDraftMixin, ReportAuthoringDraftMixin, ReportPublicationMixin, ReportDraftListingMixin):
    def __init__(self, archive, source_reader, renderer, *, limits=None, clock=None,
                 reference_verifier=None, template_service=None, prepared_context_reader=None, assist_verifier=None):
        self.archive = archive
        self.source_reader = source_reader
        self.renderer = renderer
        self.limits = self._limits(limits)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.reference_verifier = reference_verifier
        self.assist_verifier = assist_verifier
        self.template_service = template_service or ReportTemplateService()
        self.prepared_context_reader = prepared_context_reader or PreparedContextReader(archive, self.template_service)

    def create(self, actor, project_id, stage_id, *, command_id, selection, template):
        command_id = self._uuid(command_id)
        try:
            request_hash = canonical_hash({'selection': selection, 'template': template})
        except (ArchiveError, TypeError):
            raise ReportError('REPORT_INVALID') from None
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                draft_id = store.draft_id_for_command(stage_id, command_id)
                replay = self._replay_create(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                if store.intent_exists(draft_id):
                    return self._repair_create(store, draft_id, command_id, request_hash)
            snapshot = self.source_reader.read(actor, project_id, stage_id, selection)
            template_definition = self.renderer.template_definition(template)
            normalized_template = TemplateSelection(template.template_id, template.version, template_definition.options)
            snapshot_bytes = canonical_bytes(snapshot)
            snapshot_from_mapping(read_json(snapshot_bytes))
            snapshot_hash = bytes_hash(snapshot_bytes)
            created_at = self._now()
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                replay = self._replay_create(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                if store.intent_exists(draft_id):
                    return self._repair_create(store, draft_id, command_id, request_hash)
                if (selection.purpose == 'standup'
                        and selection.parent_publication_id is None
                        and repository.head() is not None
                        and repository.head() != snapshot.source_commit):
                    raise ReportError('REPORT_SOURCE_CHANGED')
                revision_payload = self._revision_payload(
                    draft_id, 1, selection, snapshot_hash, normalized_template,
                    template_definition, (), created_at, created_at, selection.parent_publication_id,
                )
                revision_hash = bytes_hash(canonical_bytes(revision_payload))
                intent = {
                    'schema_version': 1,
                    'command_id': command_id,
                    'request_hash': request_hash,
                    'project_id': project_id,
                    'stage_id': stage_id,
                    'owner_subject': actor.subject,
                    'draft_id': draft_id,
                    'snapshot_hash': snapshot_hash,
                    'created_at': created_at,
                    'selection': selection,
                    'template': normalized_template,
                    'revision_payload': revision_payload,
                    'revision_hash': revision_hash,
                }
                command = self._command_payload('create', command_id, request_hash, draft_id, None, None, revision_payload, revision_hash)
                store.write_create(
                    draft_id, command_id, request_hash=request_hash, intent=intent,
                    snapshot_bytes=snapshot_bytes, revision_payload=revision_payload,
                    revision_hash=revision_hash, command_payload=command,
                )
                return store.read_draft(draft_id, revision=1)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error) from None

    def get(self, actor, project_id, stage_id, draft_id, *, _read_view=None):
        draft_id = self._uuid(draft_id)
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False, _read_view=_read_view) as repository:
                return self._store(repository).read_draft(draft_id)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def save(self, actor, project_id, stage_id, draft_id, *, command_id, expected_revision, edits, template):
        draft_id = self._uuid(draft_id)
        command_id = self._uuid(command_id)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ReportError('REPORT_INVALID')
        try:
            requested_edits = tuple(edits or ())
            request_hash = canonical_hash({
                'draft_id': draft_id,
                'expected_revision': expected_revision,
                'edits': self._edit_requests(requested_edits),
                'template': template,
            })
        except (ArchiveError, TypeError):
            raise ReportError('REPORT_INVALID') from None
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                replay = self._replay_save(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                current = store.read_draft(draft_id)
                if current.state != 'draft':
                    raise ReportError('REPORT_FINALIZING' if current.state == 'finalizing' else 'REPORT_FINALIZED')
                if current.authoring_schema == AUTHORING_SCHEMA:
                    raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
                if current.revision != expected_revision:
                    raise ReportError('REPORT_REVISION_CONFLICT')
                if store.revision_count(draft_id) >= self.limits.max_revisions:
                    raise ReportError('REPORT_LIMIT')
                template_definition = self.renderer.template_definition(template)
                normalized_template = TemplateSelection(template.template_id, template.version, template_definition.options)
                attributed_edits = self._attributed_edits(current, validate_edit_targets(current.snapshot, requested_edits), actor)
                updated_at = self._now()
                revision_payload = self._revision_payload(
                    draft_id, current.revision + 1, current.selection, current.snapshot_hash,
                    normalized_template, template_definition, attributed_edits,
                    current.created_at, updated_at, current.parent_publication_id,
                )
                if store.edit_history_bytes(draft_id, revision_payload) > self.limits.max_edit_history_bytes:
                    raise ReportError('REPORT_LIMIT')
                revision_hash = bytes_hash(canonical_bytes(revision_payload))
                command = self._command_payload(
                    'save', command_id, request_hash, draft_id,
                    current.revision, current.revision_hash, revision_payload, revision_hash,
                )
                store.write_save_command(draft_id, command_id, revision_payload=revision_payload,
                                         revision_hash=revision_hash, command_payload=command)
                store.publish_current(draft_id, current.revision + 1, revision_hash, expected_revision=current.revision)
                return store.read_draft(draft_id)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def render(self, actor, project_id, stage_id, draft_id, *, revision):
        draft_id = self._uuid(draft_id)
        if type(revision) is not int or revision < 1:
            raise ReportError('REPORT_INVALID')
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
                store = self._store(repository)
                draft = store.read_draft(draft_id, revision=revision)
                state = self._render_state(store, draft_id, draft)
            if is_pinned_document(draft):
                return self.renderer.render_pinned(
                    draft.snapshot, draft.template_snapshot, render_edits(draft),
                    authoring_context=draft.authoring_context, draft_id=draft.draft_id,
                    revision=draft.revision, revision_hash=draft.revision_hash, edition_state=state,
                )
            if self.renderer.template_definition(draft.template) != draft.template_definition:
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
            return self.renderer.render(draft.snapshot, draft.template, render_edits(draft),
                                        draft_id=draft.draft_id, revision=draft.revision,
                                        revision_hash=draft.revision_hash, edition_state=state)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def finalization_status(self, actor, project_id, stage_id, draft_id, *, _read_view=None):
        draft_id = self._uuid(draft_id)
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False, _read_view=_read_view) as repository:
                store = self._store(repository)
                if not store.finalization_intent_exists(draft_id):
                    return None
                payload, _ = store.finalization_packet(draft_id)
                state = store.read_draft(draft_id).state
                if state not in {'finalizing', 'finalized'}:
                    raise ReportError('REPORT_ARTIFACT_INVALID')
                return ReportFinalizationStatus(
                    draft_id,
                    state,
                    payload['command_id'],
                    payload['publication_id'],
                    payload['draft_revision'],
                )
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def publication_target(self, actor, project_id, stage_id, *, _read_view=None):
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=False, _read_view=_read_view) as repository:
                archive_id = self._archive_id()
                return ReportArchiveTarget(archive_id, repository.project.id, repository.stage.id)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def _replay_create(self, store, draft_id, command_id, request_hash):
        command = store.command(draft_id, command_id)
        if command is None:
            return None
        self._verify_command(command, 'create', request_hash, draft_id, command_id)
        try:
            store.revision_payload(draft_id, command['revision'])
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            store.recover_revision(draft_id, command['revision_payload'], command['revision_hash'])
        if not store.current_exists(draft_id):
            store.publish_current(draft_id, command['revision'], command['revision_hash'], expected_revision=None)
        return store.read_draft(draft_id, revision=command['revision'])

    def _repair_create(self, store, draft_id, command_id, request_hash):
        intent = store.read_intent(draft_id)
        if intent.get('schema_version') != 1 or intent.get('command_id') != command_id or intent.get('request_hash') != request_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')
        try:
            revision_payload, revision_hash = store.revision_payload(draft_id, 1)
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            revision_payload = intent['revision_payload']
            revision_hash = intent['revision_hash']
            store.recover_revision(draft_id, revision_payload, revision_hash)
        command = self._command_payload('create', command_id, request_hash, draft_id, None, None, revision_payload, revision_hash)
        store.write_command(draft_id, command_id, command)
        if not store.current_exists(draft_id):
            store.publish_current(draft_id, 1, revision_hash, expected_revision=None)
        return store.read_draft(draft_id, revision=1)

    def _replay_save(self, store, draft_id, command_id, request_hash):
        command = store.command(draft_id, command_id)
        if command is None:
            return None
        self._verify_command(command, 'save', request_hash, draft_id, command_id)
        try:
            store.revision_payload(draft_id, command['revision'])
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            store.recover_revision(draft_id, command['revision_payload'], command['revision_hash'])
        intended = store.read_draft(draft_id, revision=command['revision'])
        try:
            current = store.read_draft(draft_id)
        except ArchiveError:
            raise
        if current.revision == command['prior_revision']:
            store.publish_current(draft_id, command['revision'], command['revision_hash'],
                                  expected_revision=command['prior_revision'])
        return intended

    def _verify_command(self, command, kind, request_hash, draft_id, command_id):
        expected = {'schema_version', 'kind', 'command_id', 'request_hash', 'draft_id', 'expected_revision',
                    'prior_revision', 'prior_revision_hash', 'revision', 'revision_hash', 'revision_payload'}
        if set(command.keys()) != expected or command['schema_version'] != 1 or command['kind'] != kind:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if command['draft_id'] != draft_id or command['command_id'] != command_id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if command['request_hash'] != request_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _attributed_edits(self, current, desired, actor):
        old = {edit.edit_id: edit for edit in current.edits}
        attributed = []
        timestamp = self._now()
        for edit in desired:
            previous = old.get(edit.edit_id)
            if previous is not None and self._same_edit_content(previous, edit):
                attributed.append(previous)
                continue
            attributed.append(replace(edit, author=actor.subject, edited_at=timestamp))
        return tuple(attributed)

    def _same_edit_content(self, left, right) -> bool:
        return (
            left.edit_id == right.edit_id
            and left.kind == right.kind
            and left.target == right.target
            and left.text == right.text
            and left.expected_original_hash == right.expected_original_hash
        )

    def _edit_requests(self, edits):
        return tuple(replace(edit, author=None, edited_at=None) for edit in edits)

    def _revision_payload(self, draft_id, revision, selection, snapshot_hash, template,
                          template_definition, edits, created_at, updated_at, parent_publication_id):
        return {
            'schema_version': 1,
            'draft_id': draft_id,
            'revision': revision,
            'selection': selection,
            'snapshot_hash': snapshot_hash,
            'template': template,
            'template_definition': template_definition,
            'edits': tuple(edits),
            'created_at': created_at,
            'updated_at': updated_at,
            'parent_publication_id': parent_publication_id,
        }

    def _command_payload(self, kind, command_id, request_hash, draft_id, prior_revision, prior_revision_hash,
                         revision_payload, revision_hash):
        return {
            'schema_version': 1,
            'kind': kind,
            'command_id': command_id,
            'request_hash': request_hash,
            'draft_id': draft_id,
            'expected_revision': prior_revision,
            'prior_revision': prior_revision,
            'prior_revision_hash': prior_revision_hash,
            'revision': revision_payload['revision'],
            'revision_hash': revision_hash,
            'revision_payload': revision_payload,
        }

    def _store(self, repository):
        return ReportDraftStore(repository, self.archive.config.root, self.archive.config.limits, self.limits)

    def _render_state(self, store, draft_id, draft):
        if draft.state != 'finalized':
            return 'draft'
        if not store.finalization_intent_exists(draft_id):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        payload, _ = store.finalization_packet(draft_id)
        return 'final' if payload['draft_revision'] == draft.revision else 'draft'

    def _archive_id(self):
        if hasattr(self.archive, '_root_id'):
            return self.archive._root_id()
        data = (self.archive.config.root / 'archive-root.json').read_bytes()
        return str(decode_json(data)['root_id'])

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ReportError('REPORT_INVALID')
        return value.astimezone(UTC).isoformat()

    def _uuid(self, value):
        try:
            return validate_uuid_text(value)
        except ReportError:
            raise ReportError('REPORT_INVALID') from None

    def _limits(self, limits):
        limits = limits or ReportDraftLimits()
        if (not isinstance(limits, ReportDraftLimits)
                or type(limits.max_edit_history_bytes) is not int
                or type(limits.max_revisions) is not int
                or limits.max_edit_history_bytes <= 0
                or limits.max_revisions <= 0):
            raise ReportError('REPORT_INVALID')
        return limits

    def _report_error(self, error, *, missing_as_not_found=False):
        code = getattr(error, 'code', '')
        if isinstance(error, ProjectError):
            return ReportError('REPORT_NOT_FOUND' if code == 'PROJECT_NOT_FOUND' else 'REPORT_SOURCE_CHANGED')
        if code == 'ARCHIVE_QUOTA_EXCEEDED':
            return ReportError('REPORT_LIMIT')
        if code in {'ARCHIVE_RAW_PAGE_MISSING'} and missing_as_not_found:
            return ReportError('REPORT_NOT_FOUND')
        if code == 'ARCHIVE_CHAIN_CONFLICT':
            return ReportError('REPORT_REVISION_CONFLICT')
        if code in {'ARCHIVE_STORAGE_UNAVAILABLE', 'ARCHIVE_READ_UNSUPPORTED'}:
            return ReportError('REPORT_STORAGE_UNAVAILABLE')
        if code in {'ARCHIVE_BUSY', 'ARCHIVE_MANIFEST_INVALID',
                    'ARCHIVE_CAPTURE_CONFLICT', 'ARCHIVE_RAW_PAGE_INTEGRITY_FAILED', 'UNSAFE_PATH'}:
            return ReportError('REPORT_ARTIFACT_INVALID')
        return ReportError('REPORT_INVALID')
