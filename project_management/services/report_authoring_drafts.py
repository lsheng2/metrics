from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_authoring import (
    AUTHORING_SCHEMA, authored_successor_selection,
    attributed_authored_edits,
    authored_edit_request_payload,
    legacy_edit_to_authored,
    normalize_authoring_template_selection,
    template_snapshot,
    user_template_selection,
)
from project_management.app.domain.report_authoring_hashes import authored_create_request_hash
from project_management.app.domain.report_assist_attribution import apply_assist_attribution, apply_assist_context
from project_management.app.domain.report_continuity_edits import apply_continuity_changes, apply_continuity_edit_requests
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import bytes_hash, canonical_hash, read_json, snapshot_from_mapping
from project_management.app.domain.report_presentation import TemplateSelection
from project_management.services.report_reference_receipts import verify_reference_requests


class ReportAuthoringDraftMixin:
    def create_authored(self, actor, project_id, stage_id, *, command_id, selection, template, preparation_id=None):
        command_id = self._uuid(command_id)
        user_selection = user_template_selection(template)
        normalized_template = None if user_selection else normalize_authoring_template_selection(template)
        try:
            prepared = self._prepared_context(actor, project_id, stage_id, command_id, selection, template, preparation_id)
            request_hash = authored_create_request_hash(
                selection, template, preparation_id, None if prepared is None else prepared.context_hash,
                None if prepared is None else prepared.preservation_hash,
            )
        except (ArchiveError, TypeError):
            raise ReportError('REPORT_INVALID') from None
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                draft_id = store.draft_id_for_command(stage_id, command_id)
                replay = self._replay_authored_create(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                if store.intent_exists(draft_id):
                    return self._repair_authored_create(store, draft_id, command_id, request_hash)
            snapshot = self.source_reader.read(actor, project_id, stage_id, selection)
            if prepared is not None:
                definition = prepared.pinned_template_use.template_definition
                normalized_template = TemplateSelection(definition.template_id, definition.version, definition.options)
            elif user_selection is None:
                definition = self.renderer.template_definition(normalized_template)
                normalized_template = type(normalized_template)(
                    normalized_template.template_id, normalized_template.version, definition.options,
                )
            else:
                definition = None
            snapshot_bytes = canonical_bytes(snapshot)
            snapshot_from_mapping(read_json(snapshot_bytes))
            snapshot_hash = bytes_hash(snapshot_bytes)
            if prepared is not None and snapshot_hash != prepared.snapshot_hash:
                raise ReportError('REPORT_SOURCE_CHANGED')
            created_at = self._now()
            if prepared is not None:
                template_data = prepared.pinned_template_use.template_snapshot
            elif user_selection is not None:
                pinned = self.template_service.use(
                    actor, project_id, command_id=command_id, draft_id=draft_id,
                    request_hash=request_hash, selection=user_selection, use_mode='standalone',
                )
                definition = pinned.template_definition
                normalized_template = TemplateSelection(definition.template_id, definition.version, definition.options)
                template_data = pinned.template_snapshot
            else:
                template_data = template_snapshot(template, normalized_template, definition)
            revision_payload = self._authored_revision_payload(
                draft_id, 1, selection, snapshot_hash, normalized_template, definition,
                () if prepared is None else prepared.initial_authored_edits,
                created_at, created_at, selection.parent_publication_id, template_data,
                None if prepared is None else prepared.context,
            )
            revision_hash = bytes_hash(canonical_bytes(revision_payload))
            intent = self._create_intent(
                actor, project_id, stage_id, command_id, request_hash,
                draft_id, snapshot_hash, created_at, selection, normalized_template,
                revision_payload, revision_hash,
            )
            command = self._command_payload(
                'create_authored', command_id, request_hash, draft_id,
                None, None, revision_payload, revision_hash,
            )
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                replay = self._replay_authored_create(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                if store.intent_exists(draft_id):
                    return self._repair_authored_create(store, draft_id, command_id, request_hash)
                if (selection.purpose == 'standup'
                        and selection.parent_publication_id is None
                        and repository.head() is not None
                        and repository.head() != snapshot.source_commit):
                    raise ReportError('REPORT_SOURCE_CHANGED')
                store.write_create(
                    draft_id, command_id, request_hash=request_hash, intent=intent,
                    snapshot_bytes=snapshot_bytes, revision_payload=revision_payload,
                    revision_hash=revision_hash, command_payload=command,
                    preparation_binding=None if prepared is None else self._preparation_binding(
                        project_id, stage_id, draft_id, command_id, request_hash, preparation_id,
                        prepared.context_hash, prepared.snapshot_hash, prepared.authority,
                        prepared.preservation_review_issues,
                    ),
                )
                return store.read_draft(draft_id, revision=1)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error) from None

    def save_authored(self, actor, project_id, stage_id, draft_id, *, command_id, expected_revision,
                      expected_revision_hash, edits, continuity_changes=()):
        draft_id = self._uuid(draft_id)
        command_id = self._uuid(command_id)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ReportError('REPORT_INVALID')
        self._input_hash(expected_revision_hash)
        try:
            requested = tuple(edits or ())
            request_hash = canonical_hash({
                'draft_id': draft_id,
                'expected_revision': expected_revision,
                'expected_revision_hash': expected_revision_hash,
                'edits': tuple(authored_edit_request_payload(edit) for edit in requested),
                'continuity_changes': tuple(continuity_changes or ()),
            })
        except (ArchiveError, TypeError):
            raise ReportError('REPORT_INVALID') from None
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = self._store(repository)
                replay = self._replay_authored_save(store, draft_id, command_id, request_hash)
                if replay is not None:
                    return replay
                current = store.read_draft(draft_id)
                if current.authoring_context is None and continuity_changes:
                    raise ReportError('REPORT_EDIT_TARGET_INVALID')
                if current.authoring_context is not None and current.authoring_context['report_role'] == 'weekly_view':
                    raise ReportError('REPORT_EDIT_TARGET_INVALID')
                self._verify_authored_current(current, expected_revision, expected_revision_hash)
                if store.revision_count(draft_id) >= self.limits.max_revisions:
                    raise ReportError('REPORT_LIMIT')
                timestamp = self._now()
                active = self._existing_authored_edits(current)
                assist_refs = {}
                if any(edit.assist_receipt_id is not None for edit in requested):
                    verifier = getattr(self, 'assist_verifier', None)
                    if verifier is None:
                        raise ReportError('REPORT_AI_UNAVAILABLE')
                    assist_refs = verifier.verify_requests(repository, current, requested)
                if current.authoring_context is None:
                    references = self._verify_reference_receipts(actor, project_id, stage_id, current, requested, active, timestamp)
                    context = current.authoring_context
                    authored_edits = attributed_authored_edits(
                        current.snapshot, active, requested, actor.subject, timestamp, references,
                        current.template_snapshot,
                    )
                else:
                    continuity_requested, standard_requested = self._split_context_edit_requests(requested)
                    continuity_active, standard_active = self._split_context_edit_requests(active)
                    continuity_references = self._verify_reference_receipts(
                        actor, project_id, stage_id, current, continuity_requested, continuity_active, timestamp,
                    )
                    context, continuity_edits = apply_continuity_edit_requests(
                        current.authoring_context, continuity_active, continuity_requested, actor.subject, timestamp,
                        continuity_references,
                    )
                    context = apply_continuity_changes(context, continuity_changes, actor.subject, timestamp)
                    references = self._verify_reference_receipts(
                        actor, project_id, stage_id, current, standard_requested, standard_active, timestamp,
                    )
                    standard_edits = attributed_authored_edits(
                        current.snapshot, standard_active, standard_requested, actor.subject, timestamp,
                        references, current.template_snapshot,
                    )
                    authored_edits = continuity_edits + standard_edits
                authored_edits = apply_assist_attribution(authored_edits, active, assist_refs)
                context = apply_assist_context(context, authored_edits)
                template_data, normalized_template, definition = self._template_for_authored_save(current)
                revision_payload = self._authored_revision_payload(
                    draft_id, current.revision + 1, current.selection, current.snapshot_hash,
                    normalized_template, definition, authored_edits,
                    current.created_at, timestamp, current.parent_publication_id, template_data, context,
                )
                if store.edit_history_bytes(draft_id, revision_payload) > self.limits.max_edit_history_bytes:
                    raise ReportError('REPORT_LIMIT')
                revision_hash = bytes_hash(canonical_bytes(revision_payload))
                command = self._command_payload(
                    'save_authored', command_id, request_hash, draft_id,
                    current.revision, current.revision_hash, revision_payload, revision_hash,
                )
                store.write_save_command(
                    draft_id, command_id, revision_payload=revision_payload,
                    revision_hash=revision_hash, command_payload=command,
                )
                store.publish_current(draft_id, current.revision + 1, revision_hash, expected_revision=current.revision)
                return store.read_draft(draft_id)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def _replay_authored_create(self, store, draft_id, command_id, request_hash):
        command = store.command(draft_id, command_id)
        if command is None:
            return None
        self._verify_command(command, 'create_authored', request_hash, draft_id, command_id)
        try:
            store.revision_payload(draft_id, command['revision'])
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            store.recover_revision(draft_id, command['revision_payload'], command['revision_hash'])
        if not store.current_exists(draft_id):
            store.publish_current(draft_id, command['revision'], command['revision_hash'], expected_revision=None)
        return store.read_draft(draft_id, revision=command['revision'])

    def _repair_authored_create(self, store, draft_id, command_id, request_hash):
        intent = store.read_intent(draft_id)
        if intent.get('command_id') != command_id or intent.get('request_hash') != request_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')
        try:
            revision_payload, revision_hash = store.revision_payload(draft_id, 1)
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            revision_payload = intent['revision_payload']
            revision_hash = intent['revision_hash']
            store.recover_revision(draft_id, revision_payload, revision_hash)
        command = self._command_payload('create_authored', command_id, request_hash, draft_id, None, None, revision_payload, revision_hash)
        store.write_command(draft_id, command_id, command)
        if not store.current_exists(draft_id):
            store.publish_current(draft_id, 1, revision_hash, expected_revision=None)
        return store.read_draft(draft_id, revision=1)

    def _replay_authored_save(self, store, draft_id, command_id, request_hash):
        command = store.command(draft_id, command_id)
        if command is None:
            return None
        self._verify_command(command, 'save_authored', request_hash, draft_id, command_id)
        try:
            store.revision_payload(draft_id, command['revision'])
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            store.recover_revision(draft_id, command['revision_payload'], command['revision_hash'])
        intended = store.read_draft(draft_id, revision=command['revision'])
        current = store.read_draft(draft_id)
        if current.revision == command['prior_revision']:
            store.publish_current(draft_id, command['revision'], command['revision_hash'],
                                  expected_revision=command['prior_revision'])
        return intended

    def _verify_authored_current(self, current, expected_revision, expected_revision_hash):
        if current.state != 'draft':
            raise ReportError('REPORT_FINALIZING' if current.state == 'finalizing' else 'REPORT_FINALIZED')
        if current.revision != expected_revision or current.revision_hash != expected_revision_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _authored_revision_payload(self, draft_id, revision, selection, snapshot_hash, template,
                                   definition, authored_edits, created_at, updated_at,
                                   parent_publication_id, template_data, authoring_context):
        return {
            'schema_version': 2,
            'draft_id': draft_id,
            'revision': revision,
            'selection': selection,
            'snapshot_hash': snapshot_hash,
            'template': template,
            'template_definition': definition,
            'edits': tuple(authored_edits),
            'created_at': created_at,
            'updated_at': updated_at,
            'parent_publication_id': parent_publication_id,
            'authoring_schema': AUTHORING_SCHEMA,
            'template_snapshot': template_data,
            'authoring_context': authoring_context,
        }

    def _create_intent(self, actor, project_id, stage_id, command_id, request_hash, draft_id, snapshot_hash,
                       created_at, selection, template, revision_payload, revision_hash):
        return {
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
            'template': template,
            'revision_payload': revision_payload,
            'revision_hash': revision_hash,
        }

    def _existing_authored_edits(self, current):
        if current.authoring_schema == AUTHORING_SCHEMA:
            return current.authored_edits
        return tuple(legacy_edit_to_authored(edit) for edit in current.edits)

    def _template_for_authored_save(self, current):
        if current.authoring_schema == AUTHORING_SCHEMA:
            return current.template_snapshot, current.template, current.template_definition
        authoring, normalized = authored_successor_selection(current.template)
        definition = self.renderer.template_definition(normalized)
        normalized = type(normalized)(normalized.template_id, normalized.version, definition.options)
        return template_snapshot(authoring, normalized, definition), normalized, definition

    def _input_hash(self, value):
        if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
            raise ReportError('REPORT_INVALID')
        return value

    def _prepared_context(self, actor, project_id, stage_id, command_id, selection, template, preparation_id):
        if preparation_id is None:
            return None
        return self.prepared_context_reader.read_for_create(
            actor,
            project_id,
            stage_id,
            command_id=command_id,
            selection=selection,
            template=template,
            preparation_id=preparation_id,
        )

    def _preparation_binding(self, project_id, stage_id, draft_id, command_id, request_hash,
                             preparation_id, context_hash, snapshot_hash, authority, preservation_review_issues=()):
        if authority is not None:
            return {
                'schema_version': 2,
                'kind': 'daily_preparation_active_slot',
                'project_id': project_id,
                'stage_id': stage_id,
                'draft_id': draft_id,
                'create_command_id': command_id,
                'request_hash': request_hash,
                'preparation_id': preparation_id,
                'preparation_intent_hash': authority['preparation_intent_hash'],
                'slot_id': authority['slot_id'],
                'slot_key': authority['slot_key'],
                'context_hash': context_hash,
                'snapshot_hash': snapshot_hash,
                'preservation_review_issues': tuple(preservation_review_issues),
            }
        return {
            'schema_version': 1,
            'kind': 'internal_prepared_context',
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft_id,
            'create_command_id': command_id,
            'request_hash': request_hash,
            'preparation_id': preparation_id,
            'context_hash': context_hash,
            'snapshot_hash': snapshot_hash,
            'preservation_review_issues': tuple(preservation_review_issues),
        }

    def _split_context_edit_requests(self, edits):
        continuity = []
        standard = []
        for edit in tuple(edits or ()):
            target = edit.target
            if isinstance(target, dict) and target.get('scope') in {'daily_note', 'report_action', 'persistent_note'}:
                continuity.append(edit)
            else:
                standard.append(edit)
        return tuple(continuity), tuple(standard)

    def _verify_reference_receipts(self, actor, project_id, stage_id, current, requested, active, timestamp):
        return verify_reference_requests(self, actor, project_id, stage_id, current, requested, active)
