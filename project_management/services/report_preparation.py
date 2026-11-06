from dataclasses import asdict
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring_hashes import (
    authored_create_template_use_request_hash,
    pinned_template_use_hash,
)
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.report_continuity import PublicationRef
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.app.domain.report_templates import UserTemplateSelection
from project_management.app.domain.run_values import capture_id as run_capture_id
from project_management.app.domain.run_values import draft_command_id as run_draft_command_id
from project_management.app.domain.run_values import operation_id as run_operation_id
from project_management.app.domain.run_values import request_hash as run_request_hash
from project_management.out.preparation_links import DjangoPreparationLinkBuilder
from project_management.services.report_continuity_preview import build_baseline_preview_from_repository
from project_management.services.report_preparation_worker import (
    daily_run_request,
    derived_ids,
    original_request_payload,
    prepare_worker_context,
    reprepare,
    _authority_from_intent,
    validate_active_preparation,
    preparation_runtime_options,
    require_preparation_runtime,
)
from project_management.services.report_preservation import reprepare_parent_draft
from project_management.services.report_preparation_results import draft_preparation_result, operation_preparation_result
from project_management.services.report_preparation_reads import get_preparation, preparation_for_meeting
from project_management.services.report_historical_references import HistoricalReferenceResolver
from project_management.storage.report_preparations import ReportPreparationStore


class ReportPreparationService:
    def __init__(self, continuity_service, draft_service, template_service, link_builder=None, run_service=None):
        self.continuity = continuity_service
        self.draft_service = draft_service
        self.template_service = template_service
        self.link_builder = link_builder or DjangoPreparationLinkBuilder()
        self.run_service = run_service
        self.archive = continuity_service.archive

    def get(self, actor, project_id, stage_id, preparation_id):
        return get_preparation(self, actor, project_id, stage_id, preparation_id)

    def for_meeting(self, actor, project_id, stage_id, *, series_id, meeting_date):
        return preparation_for_meeting(self, actor, project_id, stage_id, series_id, meeting_date)

    def runtime_options(self):
        return preparation_runtime_options(self)

    def prepare(self, actor, project_id, stage_id, *, command_id, series_id, meeting_date,
                expected_series_policy_hash, expected_baseline_ref, template_selection,
                source_mode, capture_id, analysis_mode, acknowledge_gap_draft_ids):
        request = self._request(
            command_id, series_id, meeting_date, expected_series_policy_hash,
            expected_baseline_ref, template_selection, source_mode, capture_id,
            analysis_mode, acknowledge_gap_draft_ids,
        )
        existing = self._existing_reservation(actor, project_id, stage_id, request)
        if existing is not None:
            stored, disposition = existing
            return self._compose_or_result(actor, project_id, stage_id, stored, disposition, request)
        require_preparation_runtime(self, request)
        _, stage, policy = self.continuity._read_policy_for_prepare(
            actor, project_id, stage_id, request['series_id'], request['expected_series_policy_hash'],
        )
        preview = self.continuity.preview(
            actor, project_id, stage_id, series_id=request['series_id'],
            meeting_date=request['meeting_date'], template_selection=request['template_selection'],
        )
        self._validate_preview(preview, request)
        ids = derived_ids(stage.id, request['slot_id'])
        capture_id = request['capture_id'] if request['source_mode'] == 'saved_capture' else ids['capture_id']
        selection = ReportSelection(capture_id=capture_id, timezone=policy.calendar.timezone)
        if request['source_mode'] == 'saved_capture':
            self._validate_saved_capture(actor, project_id, stage_id, selection)
        effective = self._effective_selection(
            request, preview, policy, capture_id,
        )
        intent = self._intent(
            actor, project_id, stage.id, stage.definition_hash, request, preview, effective, selection,
        )
        if request['source_mode'] == 'refresh' and self.archive.stage_archive_status(actor, project_id, stage_id) == 'absent':
            self.archive.initialize_stage(actor, project_id, stage_id)
        stored, disposition = self._reserve_new(actor, project_id, stage_id, request, intent, policy)
        return self._compose_or_result(actor, project_id, stage_id, stored, disposition, request)

    def reprepare(self, actor, project_id, stage_id, *, command_id, preparation_id,
                  expected_operation_revision, expected_draft_revision,
                  expected_draft_revision_hash, expected_baseline_ref, template_selection,
                  source_mode, capture_id, analysis_mode):
        return reprepare(
            self, actor, project_id, stage_id,
            command_id=command_id,
            preparation_id=preparation_id,
            expected_operation_revision=expected_operation_revision,
            expected_draft_revision=expected_draft_revision,
            expected_draft_revision_hash=expected_draft_revision_hash,
            expected_baseline_ref=expected_baseline_ref,
            template_selection=template_selection,
            source_mode=source_mode,
            capture_id=capture_id,
            analysis_mode=analysis_mode,
        )

    def _compose_or_result(self, actor, project_id, stage_id, stored, disposition, request):
        if stored['source_mode'] == 'refresh':
            return self._operation_result(actor, project_id, stage_id, stored, disposition, request)
        existing = self._draft_result(actor, project_id, stage_id, stored, disposition, request)
        if existing is not None:
            return existing
        policy = self.continuity._read_policy_for_prepare(
            actor, project_id, stage_id, stored['series_id'], stored['series_policy_hash'],
        )[2]
        stored_selection = self._selection_from_intent(stored, policy)
        stored_template = self._template_from_intent(stored)
        stored_baseline = self._baseline_ref(stored['expected_baseline_ref'])
        parent_draft = reprepare_parent_draft(self.draft_service, actor, project_id, stage_id, stored)
        pinned = self.template_service.use(
            actor, project_id, command_id=stored['template_use_command_id'],
            draft_id=stored['draft_id'],
            request_hash=authored_create_template_use_request_hash(
                stored_selection, stored_template, stored['preparation_id'],
            ),
            selection=stored_template,
            use_mode='continuity_prepare',
        )
        ref = self.continuity.prepare_context(
            actor, project_id, stage_id,
            preparation_id=stored['preparation_id'],
            create_command_id=stored['draft_command_id'],
            series_id=stored['series_id'],
            series_policy_hash=stored['series_policy_hash'],
            meeting_date=stored['meeting_date'],
            expected_baseline_ref=stored_baseline,
            selection=stored_selection,
            template_use_hash=pinned_template_use_hash(pinned),
            acknowledge_gap_draft_ids=tuple(stored['acknowledge_gap_draft_ids']),
            authority=_authority_from_intent(self, stored),
            preservation_parent_draft=parent_draft,
            historical_reference_resolver=HistoricalReferenceResolver(self.draft_service, actor, project_id, stage_id),
        )
        draft = self.draft_service.create_authored(
            actor, project_id, stage_id, command_id=stored['draft_command_id'],
            selection=stored_selection, template=stored_template,
            preparation_id=ref.preparation_id,
        )
        return self._result(actor, project_id, stage_id, stored, disposition, draft, request)

    def _existing_reservation(self, actor, project_id, stage_id, request):
        try:
            if self.archive.stage_archive_status(actor, project_id, stage_id) == 'absent':
                return None
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                store = ReportPreparationStore(repository, self.archive.config.root, self.archive.config.limits)
                return store.existing(request['command_id'], request['request_hash'], request['slot_id'])
        except ArchiveError as error:
            raise self.draft_service._report_error(error) from None

    def _reserve_new(self, actor, project_id, stage_id, request, intent, policy):
        try:
            with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                locked = build_baseline_preview_from_repository(self.archive, repository, policy, request['meeting_date'])
                self._validate_preview(locked, request)
                store = ReportPreparationStore(repository, self.archive.config.root, self.archive.config.limits)
                return store.reserve(request['command_id'], request['request_hash'], request['slot_id'], intent)
        except ArchiveError as error:
            raise self.draft_service._report_error(error) from None

    def _draft_result(self, actor, project_id, stage_id, intent, disposition, request):
        try:
            draft = self.draft_service.get(actor, project_id, stage_id, intent['draft_id'])
        except ReportError as error:
            if error.code == 'REPORT_NOT_FOUND':
                return None
            raise
        return self._result(actor, project_id, stage_id, intent, disposition, draft, request)

    def prepare_worker_context(self, actor, project_id, stage_id, operation, request):
        return prepare_worker_context(self, actor, project_id, stage_id, operation, request)

    def validate_active_preparation(self, actor, project_id, stage_id, target):
        return validate_active_preparation(self, actor, project_id, stage_id, target)

    def _operation_result(self, actor, project_id, stage_id, intent, disposition, request):
        if self.run_service is None:
            raise ReportError('REPORT_INVALID')
        return operation_preparation_result(self, actor, project_id, stage_id, intent, disposition, request)

    def _result(self, actor, project_id, stage_id, intent, disposition, draft, request):
        return draft_preparation_result(self, actor, project_id, stage_id, intent, disposition, draft, request)

    def _intent(self, actor, project_id, stage_id, stage_hash, request, preview, effective, selection):
        slot_id = request['slot_id']
        preparation_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f"preparation:{slot_id}"))
        operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
        derived_operation_id = run_operation_id(validate_uuid_text(str(stage_id)), operation_command_id)
        draft_command_id = run_draft_command_id(derived_operation_id)
        draft_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f'draft:{draft_command_id}'))
        intent = {
            'schema_version': 1,
            'preparation_id': preparation_id,
            'slot_id': slot_id,
            'slot_key': {'series_id': request['series_id'], 'local_date': request['meeting_date']},
            'project_id': validate_uuid_text(str(project_id)),
            'stage_id': validate_uuid_text(str(stage_id)),
            'owner_subject': actor.subject,
            'command_id': request['command_id'],
            'request_hash': request['request_hash'],
            'series_id': request['series_id'],
            'series_policy_hash': request['expected_series_policy_hash'],
            'meeting_date': request['meeting_date'],
            'meeting_key': preview.meeting_key,
            'period_key': preview.period_key,
            'timezone': selection.timezone,
            'expected_baseline_ref': self._baseline_payload(preview.baseline_ref),
            'template_selection': asdict(effective['template_selection']),
            'source_mode': 'saved_capture',
            'capture_id': selection.capture_id,
            'analysis_mode': 'manual_only',
            'acknowledge_gap_draft_ids': tuple(effective['acknowledge_gap_draft_ids']),
            'effective_selection': self._public_selection(effective),
            'effective_selection_hash': self._hash(self._public_selection(effective)),
            'operation_command_id': operation_command_id,
            'derived_operation_id': derived_operation_id,
            'operation_id': None,
            'draft_command_id': draft_command_id,
            'draft_id': draft_id,
            'template_use_command_id': str(uuid5(UUID(preparation_id), 'template-use')),
            'created_at': self.continuity._now(),
        }
        if request['source_mode'] == 'saved_capture':
            return intent
        intent = {
            **intent,
            'schema_version': 2,
            'original_request': original_request_payload(self, request),
            'stage_hash': stage_hash,
            'source_mode': 'refresh',
            'analysis_mode': request['analysis_mode'],
            'capture_id': run_capture_id(derived_operation_id),
            'operation_id': derived_operation_id,
        }
        intent['preparation_intent_hash'] = self._hash({
            key: item for key, item in intent.items() if key not in {'preparation_intent_hash', 'run_request_hash'}
        })
        intent['run_request_hash'] = run_request_hash(self._daily_run_request(intent))
        return intent

    def _request(self, command_id, series_id, meeting_date, expected_policy_hash, baseline,
                 template, source_mode, capture_id, analysis_mode, gaps):
        self._validate_modes(source_mode, capture_id, analysis_mode)
        command_id = validate_uuid_text(command_id)
        series_id = validate_uuid_text(str(series_id))
        if source_mode == 'saved_capture':
            capture_id = validate_uuid_text(capture_id)
        elif capture_id is not None:
            raise ReportError('REPORT_INVALID')
        if not isinstance(template, UserTemplateSelection):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        payload = {
            'series_id': series_id,
            'meeting_date': meeting_date,
            'expected_series_policy_hash': expected_policy_hash,
            'expected_baseline_ref': self._baseline_payload(baseline),
            'template_selection': asdict(template),
            'source_mode': source_mode,
            'capture_id': capture_id,
            'analysis_mode': analysis_mode,
            'acknowledge_gap_draft_ids': tuple(gaps),
        }
        return {
            **payload,
            'command_id': command_id,
            'template_selection': template,
            'expected_baseline_ref': baseline,
            'request_hash': self._hash(payload),
            'slot_id': str(uuid5(UUID(series_id), f"daily:{meeting_date}")),
        }

    def _effective_selection(self, request, preview, policy, capture_id):
        return {
            'series_id': request['series_id'],
            'series_policy_hash': request['expected_series_policy_hash'],
            'meeting_date': request['meeting_date'],
            'meeting_key': preview.meeting_key,
            'period_key': preview.period_key,
            'calendar_id': policy.calendar.calendar_id,
            'calendar_revision': policy.calendar.revision,
            'timezone': policy.calendar.timezone,
            'expected_baseline_ref': self._baseline_payload(request['expected_baseline_ref']),
            'template_selection': request['template_selection'],
            'source_mode': request['source_mode'],
            'capture_id': capture_id,
            'analysis_mode': request['analysis_mode'],
            'acknowledge_gap_draft_ids': tuple(request['acknowledge_gap_draft_ids']),
        }

    def _public_selection(self, selection):
        return {
            **selection,
            'template_selection': asdict(selection['template_selection']) if isinstance(selection['template_selection'], UserTemplateSelection) else selection['template_selection'],
            'acknowledge_gap_draft_ids': tuple(selection['acknowledge_gap_draft_ids']),
        }

    def _validate_preview(self, preview, request):
        if preview.series_policy_hash != request['expected_series_policy_hash']:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if self._baseline_payload(preview.baseline_ref) != self._baseline_payload(request['expected_baseline_ref']):
            raise ReportError('REPORT_BASELINE_CONFLICT')
        gaps = tuple(request['acknowledge_gap_draft_ids'])
        if preview.pending_gap_draft_ids and gaps != preview.pending_gap_draft_ids:
            raise ReportError('REPORT_BASELINE_PENDING')
        if not preview.pending_gap_draft_ids and gaps:
            raise ReportError('REPORT_BASELINE_PENDING')

    def _validate_modes(self, source_mode, capture_id, analysis_mode):
        if source_mode == 'saved_capture' and analysis_mode == 'manual_only' and capture_id is not None:
            return
        if source_mode == 'refresh' and analysis_mode in {'manual_only', 'changed_items'} and capture_id is None:
            return
        raise ReportError('REPORT_INVALID')

    def _conflicts(self, effective, requested):
        conflicts = []
        if effective['template_selection'] != asdict(requested['template_selection']):
            conflicts.append('template')
        if effective['source_mode'] != requested['source_mode'] or (
                requested['source_mode'] == 'saved_capture' and effective['capture_id'] != requested['capture_id']):
            conflicts.append('source')
        if effective['analysis_mode'] != requested['analysis_mode']:
            conflicts.append('analysis')
        if effective['expected_baseline_ref'] != self._baseline_payload(requested['expected_baseline_ref']):
            conflicts.append('baseline')
        if effective.get('series_policy_hash') != requested['expected_series_policy_hash']:
            conflicts.append('calendar')
        return tuple(conflicts)

    def _links(self, actor, project_id, stage_id, draft):
        publication_ref = None
        status = self.draft_service.finalization_status(actor, project_id, stage_id, draft.draft_id)
        if status is not None and status.state == 'finalized':
            publication = self.draft_service.get_publication(actor, project_id, stage_id, status.publication_id)
            publication_ref = PublicationRef(publication.manifest.publication_id, publication.manifest_sha256, publication.commit_id)
        links = self.link_builder.links(
            project_id, stage_id, draft.draft_id,
            None if publication_ref is None else publication_ref.publication_id,
        )
        return publication_ref, links

    def _validate_saved_capture(self, actor, project_id, stage_id, selection):
        self.draft_service.source_reader.read(actor, project_id, stage_id, selection)

    def _baseline_payload(self, value):
        return None if value is None else asdict(value)

    def _baseline_ref(self, value):
        return None if value is None else PublicationRef(**value)

    def _template_from_intent(self, intent):
        value = intent['template_selection']
        return UserTemplateSelection(value['template_id'], value['revision'], value['revision_hash'])

    def _selection_from_intent(self, intent, policy):
        return ReportSelection(
            capture_id=intent['capture_id'],
            baseline_publication_id=None,
            parent_publication_id=None,
            purpose='standup',
            timezone=policy.calendar.timezone,
        )

    def _hash(self, value):
        try:
            return sha256_bytes(canonical_bytes(value))
        except ArchiveError:
            raise ReportError('REPORT_INVALID') from None

    def _daily_run_request(self, intent):
        return daily_run_request(self, intent)
