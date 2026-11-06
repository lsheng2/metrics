from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_authoring import user_template_selection
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.report_draft_values import bytes_hash, canonical_hash, read_json, snapshot_from_mapping
from project_management.app.domain.report_presentation import TemplateSelection
from project_management.services.report_period_views import read_period_view


class ReportPeriodViewDraftMixin:
    def create_period_view(self, actor, project_id, stage_id, *, command_id, series_id, period_key,
                           selected_publication_refs, template):
        command_id = self._uuid(command_id)
        user_selection = user_template_selection(template)
        if user_selection is None:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        try:
            request_hash = canonical_hash({
                'kind': 'period_view',
                'series_id': series_id,
                'period_key': period_key,
                'selected_publication_refs': selected_publication_refs,
                'template': template,
            })
        except (ArchiveError, TypeError):
            raise ReportError('REPORT_INVALID') from None
        replay = self._period_view_replay(actor, project_id, stage_id, command_id, request_hash)
        if replay is not None:
            return replay
        revision = self.template_service.get(actor, project_id, user_selection.template_id, revision=user_selection.revision)
        if revision.revision_hash != user_selection.revision_hash or revision.document['schema_version'] != 2 or revision.document['report_kind'] != 'weekly':
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        period = read_period_view(
            self.archive, actor, project_id, stage_id, series_id=series_id,
            period_key=period_key, selected_publication_refs=selected_publication_refs,
        )
        try:
            return self._create_period_view_draft(
                actor, project_id, stage_id, command_id, request_hash, user_selection, period,
            )
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error) from None

    def _period_view_replay(self, actor, project_id, stage_id, command_id, request_hash):
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            store = self._store(repository)
            draft_id = store.draft_id_for_command(stage_id, command_id)
            replay = self._replay_authored_create(store, draft_id, command_id, request_hash)
            if replay is not None:
                return replay
            if store.intent_exists(draft_id):
                return self._repair_authored_create(store, draft_id, command_id, request_hash)
        return None

    def _create_period_view_draft(self, actor, project_id, stage_id, command_id, request_hash, user_selection, period):
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            store = self._store(repository)
            draft_id = store.draft_id_for_command(stage_id, command_id)
            replay = self._replay_authored_create(store, draft_id, command_id, request_hash)
            if replay is not None:
                return replay
            if store.intent_exists(draft_id):
                return self._repair_authored_create(store, draft_id, command_id, request_hash)
        selection = ReportSelection(period.source_snapshot.capture_id, purpose='historical_export', timezone=period.source_snapshot.timezone)
        pinned = self.template_service.use(
            actor, project_id, command_id=command_id, draft_id=draft_id,
            request_hash=request_hash, selection=user_selection, use_mode='continuity_prepare',
        )
        definition = pinned.template_definition
        normalized_template = TemplateSelection(definition.template_id, definition.version, definition.options)
        snapshot_bytes = canonical_bytes(period.source_snapshot)
        snapshot_from_mapping(read_json(snapshot_bytes))
        snapshot_hash = bytes_hash(snapshot_bytes)
        created_at = self._now()
        revision_payload = self._authored_revision_payload(
            draft_id, 1, selection, snapshot_hash, normalized_template, definition,
            (), created_at, created_at, None, pinned.template_snapshot, period.weekly_context,
        )
        revision_hash = bytes_hash(canonical_bytes(revision_payload))
        intent = self._create_intent(
            actor, project_id, stage_id, command_id, request_hash,
            draft_id, snapshot_hash, created_at, selection, normalized_template,
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
