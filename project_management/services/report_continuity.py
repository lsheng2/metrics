from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

from django.db import transaction
from django.db.models import F

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_continuity import (
    PreparedContextRef,
    PublicationRef,
    build_daily_authoring_context,
    meeting_identity,
    meeting_key,
    period_identity,
    period_key,
)
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_series import (
    ReportContinuityLimits,
    SeriesPage,
    payload_for_series_policy,
    series_policy_from_payload,
)
from project_management.app.domain.report_templates import UserTemplateSelection, revision_from_payload
from project_management.models import Project, ProjectAuditEvent, ProjectStage
from project_management.models_report_series import ReportSeries, ReportSeriesCommand, ReportSeriesPolicyRevisionRecord
from project_management.models_report_templates import ReportTemplate, ReportTemplateRevisionRecord
from project_management.out.orm_repository import storage_errors
from project_management.services.report_continuity_seed_binding import binding_from_seed, build_context_seed, seed_binding
from project_management.services.report_publication_reads import ReportPublicationReader
from project_management.services.report_preparation_seed import validate_prepared_context_seed
from project_management.services.report_templates import ReportTemplateService
from project_management.services.report_period_views import read_period_view
from project_management.services.report_continuity_preview import build_baseline_preview
from project_management.services.report_preservation import preserve_parent_content, preserve_publication_content
from project_management.services.report_meetings import ReportMeetingService, require_meeting_available
from project_management.services.report_meeting_snapshot import freeze_meeting_snapshot
from project_management.services.report_continuity_replay import replay_prepared_context
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import read_bytes, write_bytes


class ReportContinuityService:
    def __init__(self, archive=None, source_reader=None, *, template_service=None, limits=None, clock=None):
        self.archive = archive
        self.source_reader = source_reader
        self.template_service = template_service or ReportTemplateService()
        self.limits = limits or ReportContinuityLimits()
        self.clock = clock or (lambda: datetime.now(UTC))

    def create_series(self, actor, project_id, stage_id, *, command_id, name, calendar, template_selection):
        request_hash = self._hash({'kind': 'create_series', 'stage_id': str(stage_id), 'name': name, 'calendar': asdict(calendar), 'template': asdict(template_selection)})
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_policy(project, command_id, 'create_series', request_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            stage = self._stage(project, stage_id)
            self._verified_matrix_template(project, template_selection, require_active=True)
            if ReportSeries.objects.filter(project=project, stage=stage).count() >= self.limits.max_series_per_stage:
                raise ReportError('REPORT_LIMIT')
            series = ReportSeries.objects.create(project=project, stage=stage)
            revision = self._append_policy(series, project, stage, actor, 1, name, calendar, template_selection)
            series.current_revision = 1
            series.save(update_fields=['current_revision'])
            self._command(project, command_id, 'create_series', request_hash, revision)
            self._audit(project, stage, actor, 'report_series_created')
            return revision

    def save_series_policy(self, actor, project_id, stage_id, *, command_id, series_id,
                           expected_revision, expected_revision_hash, name, calendar, template_selection):
        request_hash = self._hash({
            'kind': 'save_series_policy', 'stage_id': str(stage_id), 'series_id': str(series_id),
            'expected_revision': expected_revision, 'expected_revision_hash': expected_revision_hash,
            'name': name, 'calendar': asdict(calendar), 'template': asdict(template_selection),
        })
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_policy(project, command_id, 'save_series_policy', request_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            stage = self._stage(project, stage_id)
            series = self._series(project, stage, series_id)
            current = self._policy(series, series.current_revision)
            if current.revision != expected_revision or current.revision_hash != expected_revision_hash:
                raise ReportError('REPORT_REVISION_CONFLICT')
            self._enforce_calendar_identity(current.calendar, calendar)
            self._verified_matrix_template(project, template_selection, require_active=True)
            if ReportSeriesPolicyRevisionRecord.objects.filter(series=series).count() >= self.limits.max_policy_revisions:
                raise ReportError('REPORT_LIMIT')
            revision = self._append_policy(series, project, stage, actor, current.revision + 1, name, calendar, template_selection)
            series.current_revision = revision.revision
            series.save(update_fields=['current_revision'])
            self._command(project, command_id, 'save_series_policy', request_hash, revision)
            self._audit(project, stage, actor, 'report_series_policy_saved')
            return revision

    def list_series(self, actor, project_id, stage_id, *, limit=20, offset=0):
        if type(limit) is not int or type(offset) is not int or limit < 1 or limit > 100 or offset < 0:
            raise ReportError('REPORT_LIMIT')
        with storage_errors():
            project = self._owned(actor, project_id)
            stage = self._stage(project, stage_id)
            rows = tuple(ReportSeries.objects.filter(project=project, stage=stage)[offset:offset + limit + 1])
            return SeriesPage(tuple(self._policy(row, row.current_revision) for row in rows[:limit]), offset + limit if len(rows) > limit else None)

    def get_series_policy(self, actor, project_id, stage_id, *, series_id, revision):
        with storage_errors():
            project = self._owned(actor, project_id)
            stage = self._stage(project, stage_id)
            return self._policy(self._series(project, stage, series_id), revision)

    def preview(self, actor, project_id, stage_id, *, series_id, meeting_date, template_selection):
        with storage_errors():
            project = self._owned(actor, project_id)
            stage = self._stage(project, stage_id)
            series = self._series(project, stage, series_id)
            policy = self._policy(series, series.current_revision)
            self._verified_matrix_template(project, template_selection, require_active=True)
            if asdict(template_selection) != asdict(policy.default_template_selection):
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        try:
            preview = build_baseline_preview(self.archive, actor, project_id, stage_id, policy, meeting_date)
            return replace(preview, meeting_skipped=ReportMeetingService(self).is_skipped(
                actor, project_id, stage_id, series_id, meeting_date,
            ))
        except ArchiveError as error:
            raise self._report_error(error) from None

    def read_period(self, actor, project_id, stage_id, *, series_id, period_key, selected_publication_refs):
        return read_period_view(self.archive, actor, project_id, stage_id, series_id=series_id, period_key=period_key, selected_publication_refs=selected_publication_refs)
    def prepare_context(self, actor, project_id, stage_id, *, preparation_id, create_command_id,
                        series_id, series_policy_hash, meeting_date, expected_baseline_ref,
                        selection, template_use_hash, acknowledge_gap_draft_ids=(), authority=None,
                        preservation_parent_draft=None, historical_reference_resolver=None):
        preparation_id = validate_uuid_text(preparation_id)
        create_command_id = validate_uuid_text(create_command_id)
        template_use_hash = validate_hash_text(template_use_hash)
        draft_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f'draft:{create_command_id}'))
        project, stage, policy = self._read_policy_for_prepare(actor, project_id, stage_id, series_id, series_policy_hash)
        meeting = meeting_identity(policy.calendar, meeting_date)
        period = period_identity(meeting)
        replay = replay_prepared_context(
            self, self._existing_seed(actor, project_id, stage_id, preparation_id), actor, project_id, stage_id,
            preparation_id=preparation_id, create_command_id=create_command_id, draft_id=draft_id,
            series_id=series_id, series_policy_hash=series_policy_hash, expected_baseline_ref=expected_baseline_ref,
            selection=selection, template_use_hash=template_use_hash, meeting=meeting, period=period,
            authority=authority, acknowledge_gap_draft_ids=acknowledge_gap_draft_ids,
            preservation_parent_draft=preservation_parent_draft,
        )
        if replay is not None:
            return replay
        require_meeting_available(self, actor, project_id, stage_id, series_id, meeting_date)
        pinned = self.template_service.read_use(actor, project_id, draft_id=draft_id, template_use_hash=template_use_hash)
        if pinned.template_snapshot['selection'] != asdict(policy.default_template_selection):
            raise ReportError('REPORT_CONTEXT_REQUIRED')
        if self.archive is None or self.source_reader is None:
            raise ReportError('REPORT_INVALID')
        snapshot = self.source_reader.read(actor, project_id, stage_id, selection)
        baseline_context, baseline_ref = self._baseline(actor, project_id, stage_id, expected_baseline_ref)
        context = build_daily_authoring_context(
            series_id=policy.series_id, series_policy_revision=policy.revision,
            series_policy_hash=policy.revision_hash, meeting=meeting, source_snapshot=snapshot,
            matrix_options=self._matrix_options(pinned.template_snapshot), baseline_context=baseline_context,
            base_daily_publication=baseline_ref,
            acknowledged_gap_draft_ids=acknowledge_gap_draft_ids,
        )
        context = freeze_meeting_snapshot(self, actor, project_id, stage_id, context, baseline_context)
        if preservation_parent_draft is not None:
            preserved = preserve_parent_content(
                preservation_parent_draft, context, pinned.template_snapshot, historical_reference_resolver,
            )
        elif baseline_ref is not None:
            with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
                preserved = preserve_publication_content(repository, baseline_ref, context, pinned.template_snapshot)
        else:
            preserved = preserve_parent_content(None, context, pinned.template_snapshot)
        context = preserved.context
        expected_binding = seed_binding(self, actor, project_id, stage_id, preparation_id, create_command_id, draft_id, series_id, series_policy_hash, expected_baseline_ref, selection, template_use_hash, meeting, period, authority, preserved.preservation)
        existing = self._existing_seed(actor, project_id, stage_id, preparation_id)
        if existing is not None:
            self._verify_existing_seed(existing, expected_binding)
            return PreparedContextRef(existing['preparation_id'], existing['context_hash'], existing['draft_id'])
        seed = self._seed(expected_binding, project, stage, policy, meeting, pinned, snapshot, context)
        return self._write_seed(actor, project_id, stage_id, seed)

    def _append_policy(self, series, project, stage, actor, revision, name, calendar, template_selection):
        payload = payload_for_series_policy(series.id, revision, project.id, stage.id, stage.definition_hash, actor.subject, self._now(), name, calendar, template_selection)
        value = series_policy_from_payload(payload)
        ReportSeriesPolicyRevisionRecord.objects.create(series=series, revision=revision, payload_json=payload, payload_hash=value.revision_hash)
        return value

    def _command(self, project, command_id, kind, request_hash, revision):
        payload = {'policy_payload': self._policy_payload(revision), 'series_id': revision.series_id}
        ReportSeriesCommand.objects.create(
            project=project, command=validate_uuid_text(command_id), kind=kind, request_hash=request_hash,
            result_series_id=revision.series_id, result_revision=revision.revision,
            result_hash=revision.revision_hash, payload_json=payload, payload_hash=self._hash(payload),
        )

    def _replay_policy(self, project, command_id, kind, request_hash):
        command = ReportSeriesCommand.objects.filter(project=project, command=validate_uuid_text(command_id)).first()
        if command is None:
            return None
        if command.kind != kind or command.request_hash != request_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if command.payload_hash != self._artifact_hash(command.payload_json):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        revision = self._policy(command.result_series, command.result_revision)
        if (revision.revision_hash != command.result_hash or command.payload_json.get('series_id') != revision.series_id
                or command.payload_json.get('policy_payload') != self._policy_payload(revision)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return revision

    def _policy(self, series, revision):
        record = ReportSeriesPolicyRevisionRecord.objects.filter(series=series, revision=revision).first()
        if record is None:
            raise ReportError('REPORT_NOT_FOUND')
        value = series_policy_from_payload(record.payload_json)
        if value.revision_hash != record.payload_hash:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value

    def _verified_matrix_template(self, project, selection, *, require_active):
        if not isinstance(selection, UserTemplateSelection):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        template = ReportTemplate.objects.filter(project=project, id=validate_uuid_text(selection.template_id)).first()
        if template is None:
            raise ProjectError('PROJECT_NOT_FOUND')
        if require_active and template.archived:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        record = ReportTemplateRevisionRecord.objects.filter(template=template, revision=selection.revision).first()
        if record is None:
            raise ReportError('REPORT_NOT_FOUND')
        revision = revision_from_payload(record.payload_json)
        if revision.revision_hash != record.payload_hash or revision.revision_hash != selection.revision_hash or revision.readiness != 'ready':
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        if revision.document['schema_version'] != 2:
            raise ReportError('REPORT_CONTEXT_REQUIRED')
        if sum(1 for block in revision.document['blocks'] if block['kind'] == 'data' and block['source'] == 'meeting_matrix') != 1:
            raise ReportError('REPORT_CONTEXT_REQUIRED')
        return revision

    def _read_policy_for_prepare(self, actor, project_id, stage_id, series_id, series_policy_hash):
        with storage_errors():
            project = self._owned(actor, project_id)
            stage = self._stage(project, stage_id)
            series = self._series(project, stage, series_id)
            record = ReportSeriesPolicyRevisionRecord.objects.filter(series=series, payload_hash=series_policy_hash).first()
            if record is None:
                raise ReportError('REPORT_REVISION_CONFLICT')
            policy = self._policy(series, record.revision)
            self._verified_matrix_template(project, policy.default_template_selection, require_active=False)
            return project, stage, policy

    def _baseline(self, actor, project_id, stage_id, expected):
        if expected is None:
            return None, None
        if not isinstance(expected, PublicationRef):
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
            publication = ReportPublicationReader(repository).get(expected.publication_id, actor.subject)
            if publication.manifest_sha256 != expected.manifest_hash or publication.commit_id != expected.commit:
                raise ReportError('REPORT_HISTORY_UNAVAILABLE')
            context = None
            if publication.manifest.schema_version == 2:
                edits = decode_json(repository.read_file(f'report_publications/{expected.publication_id}/edits.json', expected.commit))
                context = edits.get('authoring_context')
            if context is None:
                raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        return context, expected

    def _existing_seed(self, actor, project_id, stage_id, preparation_id):
        if self.archive is None:
            return None
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            try:
                return decode_json(read_bytes(repository.runtime, f'report-preparations/{preparation_id}/context.json', limit=self.limits.max_context_bytes + 8192))
            except ArchiveError as error:
                if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                    return None
                raise self._report_error(error) from None

    def _write_seed(self, actor, project_id, stage_id, seed):
        data = canonical_bytes(seed)
        if len(canonical_bytes(seed['context'])) > self.limits.max_context_bytes:
            raise ReportError('REPORT_LIMIT')
        with self.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            existing = self._read_seed(repository, seed['preparation_id'])
            if existing is not None:
                self._verify_existing_seed(existing, self._binding_from_seed(seed))
                return PreparedContextRef(existing['preparation_id'], existing['context_hash'], existing['draft_id'])
            require_meeting_available(self, actor, project_id, stage_id, seed['series_id'], seed['context']['meeting']['local_date'])
            root = repository.runtime / 'report-preparations' / seed['preparation_id']
            admit(self.archive.config.root, repository.stage_root, root, self.archive.config.limits, GrowthEstimate(len(data) + 8192, 4))
            try:
                write_bytes(repository.runtime, f"report-preparations/{seed['preparation_id']}/context.json", data, immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')
            except ArchiveError as error:
                raise self._report_error(error) from None
        return PreparedContextRef(seed['preparation_id'], seed['context_hash'], seed['draft_id'])

    def _read_seed(self, repository, preparation_id):
        try:
            return decode_json(read_bytes(repository.runtime, f'report-preparations/{preparation_id}/context.json', limit=self.limits.max_context_bytes + 8192))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                return None
            raise

    def _seed(self, binding, project, stage, policy, meeting, pinned, snapshot, context):
        return build_context_seed(self, binding, stage, policy, meeting, pinned, snapshot, context)

    def _verify_existing_seed(self, seed, binding):
        validate_prepared_context_seed(seed)
        if binding_from_seed(seed) != binding:
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _matrix_options(self, template_snapshot):
        for block in template_snapshot['resolved_document']['blocks']:
            if block['kind'] == 'data' and block['source'] == 'meeting_matrix':
                return block['options']
        raise ReportError('REPORT_CONTEXT_REQUIRED')

    def _policy_payload(self, revision):
        return payload_for_series_policy(revision.series_id, revision.revision, revision.project_id, revision.stage_id, revision.stage_hash, revision.created_by, revision.created_at, revision.name, revision.calendar, revision.default_template_selection)

    def _enforce_calendar_identity(self, current, proposed):
        if current.calendar_id == proposed.calendar_id and current.revision == proposed.revision and asdict(current) != asdict(proposed):
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _owned(self, actor, project_id):
        try:
            return Project.objects.get(id=validate_uuid_text(str(project_id)), owner_subject=actor.subject)
        except Project.DoesNotExist:
            raise ProjectError('PROJECT_NOT_FOUND') from None

    def _lock_active(self, actor, project_id):
        identity = validate_uuid_text(str(project_id))
        updated = Project.objects.filter(id=identity, owner_subject=actor.subject, archived=False).update(revision=F('revision') + 1)
        if updated:
            return self._owned(actor, identity)
        project = self._owned(actor, identity)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        raise ProjectError('PROJECT_NOT_FOUND')

    def _stage(self, project, stage_id):
        try:
            return ProjectStage.objects.get(id=validate_uuid_text(str(stage_id)), project=project)
        except ProjectStage.DoesNotExist:
            raise ProjectError('PROJECT_NOT_FOUND') from None

    def _series(self, project, stage, series_id):
        try:
            return ReportSeries.objects.get(id=validate_uuid_text(str(series_id)), project=project, stage=stage)
        except ReportSeries.DoesNotExist:
            raise ReportError('REPORT_NOT_FOUND') from None

    def _audit(self, project, stage, actor, kind):
        ProjectAuditEvent.objects.create(project=project, stage_id=stage.id, kind=kind, actor_subject=actor.subject)

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ReportError('REPORT_INVALID')
        return value.astimezone(UTC).isoformat()

    def _hash(self, value):
        try:
            return sha256_bytes(canonical_bytes(value))
        except ArchiveError:
            raise ReportError('REPORT_INVALID') from None

    def _artifact_hash(self, value):
        try:
            return sha256_bytes(canonical_bytes(value))
        except ArchiveError:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _report_error(self, error):
        code = getattr(error, 'code', '')
        if code == 'ARCHIVE_QUOTA_EXCEEDED':
            return ReportError('REPORT_LIMIT')
        if code in {'ARCHIVE_CAPTURE_CONFLICT', 'ARCHIVE_CHAIN_CONFLICT'}:
            return ReportError('REPORT_REVISION_CONFLICT')
        if code in {'ARCHIVE_RAW_PAGE_MISSING', 'ARCHIVE_MANIFEST_INVALID', 'ARCHIVE_STORAGE_UNAVAILABLE', 'UNSAFE_PATH'}:
            return ReportError('REPORT_ARTIFACT_INVALID')
        return ReportError('REPORT_INVALID')
