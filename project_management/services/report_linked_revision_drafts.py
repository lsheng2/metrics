from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_authoring import validate_template_snapshot
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.report_draft_values import bytes_hash, canonical_hash, read_json, revision_from_mapping, snapshot_from_mapping
from project_management.app.domain.report_presentation import TemplateDefinition, TemplateSelection
from project_management.app.domain.report_publication_contracts import publication_path
from project_management.services.report_daily_baseline import publication_ref as publication_ref_payload
from project_management.services.report_preservation import wrap_publication_reference_edits
from project_management.services.report_publication_reads import ReportPublicationReader


class ReportLinkedRevisionDraftMixin:
    def create_linked_revision(self, actor, project_id, stage_id, *, command_id, publication_ref):
        command_id = self._uuid(command_id)
        try:
            request_hash = canonical_hash({'kind': 'linked_revision', 'publication_ref': publication_ref})
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
            parent = self._linked_parent(actor, project_id, stage_id, publication_ref)
            return self._write_linked_revision(actor, project_id, stage_id, command_id, request_hash, draft_id, parent)
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error) from None

    def _linked_parent(self, actor, project_id, stage_id, publication_ref):
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
            publication = ReportPublicationReader(repository).get(publication_ref.publication_id, actor.subject)
            if (publication.manifest_sha256 != publication_ref.manifest_hash
                    or publication.commit_id != publication_ref.commit
                    or publication.manifest.schema_version != 2
                    or publication.manifest.report_role != 'daily'):
                raise ReportError('REPORT_HISTORY_UNAVAILABLE')
            snapshot_bytes = repository.read_file(publication_path(publication.manifest.publication_id, 'snapshot.json'), publication.commit_id)
            template_snapshot = validate_template_snapshot(decode_json(repository.read_file(publication_path(publication.manifest.publication_id, 'template.json'), publication.commit_id)))
            edits = decode_json(repository.read_file(publication_path(publication.manifest.publication_id, 'edits.json'), publication.commit_id))
        context = edits.get('authoring_context')
        if context is None:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        context = {**context, 'base_daily_publication': publication_ref_payload(publication)}
        selected = next(item for item in edits['revisions'] if item['revision'] == edits['selected_revision'])
        revision_payload = revision_from_mapping(selected['payload'])
        return publication, snapshot_bytes, template_snapshot, context, wrap_publication_reference_edits(publication, revision_payload['edits'])

    def _write_linked_revision(self, actor, project_id, stage_id, command_id, request_hash, draft_id, parent):
        publication, snapshot_bytes, template_snapshot, context, edits = parent
        snapshot = snapshot_from_mapping(read_json(snapshot_bytes))
        selection = ReportSelection(
            snapshot.capture_id,
            snapshot.baseline_publication_id,
            publication.manifest.publication_id,
            'standup',
            snapshot.timezone,
        )
        definition = TemplateDefinition(
            template_snapshot['selection']['template_id'],
            str(template_snapshot['selection']['revision']),
            {},
            template_snapshot['presentation_hash'],
            template_snapshot['renderer_version'],
        )
        template = TemplateSelection(definition.template_id, definition.version, definition.options)
        snapshot_hash = bytes_hash(snapshot_bytes)
        created_at = self._now()
        revision_payload = self._authored_revision_payload(
            draft_id, 1, selection, snapshot_hash, template, definition,
            edits, created_at, created_at, publication.manifest.publication_id,
            template_snapshot, context,
        )
        revision_hash = bytes_hash(canonical_bytes(revision_payload))
        intent = self._create_intent(
            actor, project_id, stage_id, command_id, request_hash,
            draft_id, snapshot_hash, created_at, selection, template,
            revision_payload, revision_hash,
        )
        command = self._command_payload('create_authored', command_id, request_hash, draft_id, None, None, revision_payload, revision_hash)
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            store = self._store(repository)
            replay = self._replay_authored_create(store, draft_id, command_id, request_hash)
            if replay is not None:
                return replay
            if store.intent_exists(draft_id):
                return self._repair_authored_create(store, draft_id, command_id, request_hash)
            store.write_create(
                draft_id, command_id, request_hash=request_hash, intent=intent,
                snapshot_bytes=snapshot_bytes, revision_payload=revision_payload,
                revision_hash=revision_hash, command_payload=command,
            )
            return store.read_draft(draft_id, revision=1)
