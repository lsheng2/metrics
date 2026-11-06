from dataclasses import asdict
from datetime import UTC, datetime

from django.db import transaction
from django.db.models import F

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.app.domain.report_templates import (
    ReportTemplateLimits,
    PinnedTemplateUse,
    TemplatePage,
    TemplateSummary,
    UserTemplateSelection,
    copy_document_and_policy,
    payload_for_revision,
    revision_from_payload,
    template_definition,
    template_snapshot,
    validate_report_template_revision,
)
from project_management.models import Project, ProjectAuditEvent
from project_management.models_report_templates import (
    ReportTemplate,
    ReportTemplateCommand,
    ReportTemplateRevisionRecord,
    ReportTemplateUsage,
    ReportTemplateUse,
)
from project_management.out.orm_repository import storage_errors
from project_management.services.report_template_uses import read_pinned_template_use

class ReportTemplateService:
    def __init__(self, limits=None, clock=None):
        self.limits = limits or ReportTemplateLimits()
        self.clock = clock or (lambda: datetime.now(UTC))
    def list(self, actor, project_id, *, limit=20, offset=0):
        if type(limit) is not int or type(offset) is not int or limit < 1 or offset < 0:
            raise ReportError('REPORT_INVALID')
        if limit > 100:
            raise ReportError('REPORT_LIMIT')
        with storage_errors():
            project = self._owned(actor, project_id)
            rows = list(ReportTemplate.objects.filter(project=project)[offset:offset + limit + 1])
            items = tuple(self._summary(row) for row in rows[:limit])
            return TemplatePage(items, offset + limit if len(rows) > limit else None)
    def get(self, actor, project_id, template_id, *, revision):
        with storage_errors():
            project = self._owned(actor, project_id)
            return self._revision(self._template(project, template_id), revision)
    def create(self, actor, project_id, *, command_id, name, document, fill_policy):
        validated = validate_report_template_revision(name, document, fill_policy)
        request_hash = self._hash({'kind': 'create', 'name': validated.name, 'document': validated.document, 'fill_policy': validated.fill_policy})
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_revision(project, command_id, 'create', request_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            if ReportTemplate.objects.filter(project=project).count() >= self.limits.max_templates:
                raise ReportError('REPORT_LIMIT')
            template = ReportTemplate.objects.create(project=project)
            revision = self._append_revision(template, project, actor, 1, validated)
            template.current_revision = 1
            template.save(update_fields=['current_revision'])
            self._command(project, command_id, 'create', request_hash, revision)
            self._audit(project, actor, 'template_created')
            self._refresh_usage(project)
            return revision
    def save(self, actor, project_id, template_id, *, command_id, expected_revision, expected_revision_hash, name, document, fill_policy):
        validated = validate_report_template_revision(name, document, fill_policy)
        request_hash = self._hash({
            'kind': 'save', 'template_id': template_id, 'expected_revision': expected_revision,
            'expected_revision_hash': expected_revision_hash, 'name': validated.name,
            'document': validated.document, 'fill_policy': validated.fill_policy,
        })
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_revision(project, command_id, 'save', request_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            template = self._template(project, template_id)
            if template.archived:
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
            current = self._revision(template, template.current_revision)
            self._cas(current, expected_revision, expected_revision_hash)
            if ReportTemplateRevisionRecord.objects.filter(template=template).count() >= self.limits.max_revisions:
                raise ReportError('REPORT_LIMIT')
            revision = self._append_revision(template, project, actor, template.current_revision + 1, validated)
            template.current_revision = revision.revision
            template.save(update_fields=['current_revision'])
            self._command(project, command_id, 'save', request_hash, revision)
            self._audit(project, actor, 'template_saved')
            self._refresh_usage(project)
            return revision

    def copy(self, actor, source_project_id, template_id, *, revision, target_project_id, command_id, name):
        request_hash = self._hash({
            'kind': 'copy', 'source_project_id': source_project_id, 'template_id': template_id,
            'revision': revision, 'target_project_id': target_project_id, 'name': name,
        })
        with storage_errors(), transaction.atomic():
            source_project = self._owned(actor, source_project_id)
            target_project = self._owned(actor, target_project_id)
            replay = self._replay_revision(target_project, command_id, 'copy', request_hash)
            if replay is not None:
                return replay
            source_project = self._lock_active(actor, source_project_id)
            target_project = source_project if str(source_project.id) == self._project_uuid(target_project_id) else self._lock_active(actor, target_project_id)
            if ReportTemplate.objects.filter(project=target_project).count() >= self.limits.max_templates:
                raise ReportError('REPORT_LIMIT')
            source = self._revision(self._template(source_project, template_id), revision)
            copied_document, copied_policy = copy_document_and_policy(source.document, source.fill_policy)
            validated = validate_report_template_revision(name, copied_document, copied_policy)
            template = ReportTemplate.objects.create(project=target_project)
            copied = self._append_revision(template, target_project, actor, 1, validated)
            template.current_revision = 1
            template.save(update_fields=['current_revision'])
            self._command(target_project, command_id, 'copy', request_hash, copied)
            self._audit(target_project, actor, 'template_copied')
            self._refresh_usage(target_project)
            return copied

    def archive(self, actor, project_id, template_id, *, command_id, expected_revision, expected_revision_hash):
        request_hash = self._hash({
            'kind': 'archive', 'template_id': template_id, 'expected_revision': expected_revision,
            'expected_revision_hash': expected_revision_hash,
        })
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_summary(project, command_id, 'archive', request_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            template = self._template(project, template_id)
            current = self._revision(template, template.current_revision)
            self._cas(current, expected_revision, expected_revision_hash)
            if not template.archived:
                template.archived = True
                template.save(update_fields=['archived'])
            summary = self._summary_from_revision(current, True)
            self._command(project, command_id, 'archive', request_hash, current, summary=summary)
            self._audit(project, actor, 'template_archived')
            self._refresh_usage(project)
            return summary

    def use(self, actor, project_id, *, command_id, draft_id, request_hash, selection, use_mode):
        selection = self._selection(selection)
        draft_id = validate_uuid_text(draft_id)
        self._hash_text(request_hash)
        command_hash = self._hash({
            'kind': 'use', 'draft_id': draft_id, 'request_hash': request_hash,
            'selection': asdict(selection), 'use_mode': use_mode,
        })
        with storage_errors(), transaction.atomic():
            project = self._owned(actor, project_id)
            replay = self._replay_use(project, command_id, 'use', command_hash)
            if replay is not None:
                return replay
            project = self._lock_active(actor, project_id)
            if use_mode not in {'standalone', 'continuity_prepare'}:
                raise ReportError('REPORT_INVALID')
            template = self._template(project, selection.template_id)
            if template.archived:
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
            revision = self._revision(template, selection.revision)
            if revision.revision_hash != selection.revision_hash or revision.readiness != 'ready':
                raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
            if ((use_mode == 'standalone' and revision.document['schema_version'] != 1)
                    or (use_mode == 'continuity_prepare' and revision.document['schema_version'] != 2)):
                raise ReportError('REPORT_CONTEXT_REQUIRED')
            snapshot = template_snapshot(selection, revision)
            definition = template_definition(revision)
            payload = {
                'command_id': validate_uuid_text(command_id),
                'draft_id': draft_id,
                'request_hash': request_hash,
                'template_snapshot': snapshot,
                'template_definition': asdict(definition),
            }
            ReportTemplateUse.objects.create(
                project=project, command=command_id, draft_id=draft_id, template=template,
                revision=revision.revision, revision_hash=revision.revision_hash,
                snapshot_json=payload, snapshot_hash=self._hash(payload), request_hash=request_hash,
            )
            self._command(project, command_id, 'use', command_hash, revision, use_payload=payload)
            self._audit(project, actor, 'template_used')
            self._refresh_usage(project)
            return PinnedTemplateUse(validate_uuid_text(command_id), draft_id, request_hash, snapshot, definition)

    def read_use(self, actor, project_id, *, draft_id, template_use_hash):
        with storage_errors():
            return read_pinned_template_use(self._owned(actor, project_id), draft_id=draft_id, template_use_hash=template_use_hash)

    def _append_revision(self, template, project, actor, revision, validated):
        payload = payload_for_revision(template.id, revision, project.id, actor.subject, self._now(), validated)
        saved = revision_from_payload(payload)
        ReportTemplateRevisionRecord.objects.create(
            template=template, revision=revision, payload_json=payload, payload_hash=saved.revision_hash,
        )
        return saved

    def _command(self, project, command_id, kind, request_hash, revision, use_payload=None, summary=None):
        payload = {
            'revision_payload': self._revision_payload(revision),
            'template_id': revision.template_id,
            'use_payload': use_payload,
            'summary': None if summary is None else asdict(summary),
        }
        ReportTemplateCommand.objects.create(
            project=project, command=validate_uuid_text(command_id), kind=kind, request_hash=request_hash,
            result_template_id=revision.template_id, result_revision=revision.revision,
            result_hash=revision.revision_hash, payload_json=payload, payload_hash=self._hash(payload),
        )

    def _read_command(self, project, command_id, kind, request_hash):
        command = ReportTemplateCommand.objects.filter(project=project, command=validate_uuid_text(command_id)).first()
        if command is None:
            return None
        if command.kind != kind or command.request_hash != request_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if command.payload_hash != self._artifact_hash(command.payload_json):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return command

    def _replay_revision(self, project, command_id, kind, request_hash):
        command = self._read_command(project, command_id, kind, request_hash)
        if command is None:
            return None
        return self._command_revision(project, command)

    def _replay_summary(self, project, command_id, kind, request_hash):
        command = self._read_command(project, command_id, kind, request_hash)
        if command is None:
            return None
        revision = self._command_revision(project, command)
        summary = self._summary_payload(command.payload_json.get('summary'))
        if summary != self._summary_from_revision(revision, True):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return summary

    def _replay_use(self, project, command_id, kind, request_hash):
        command = self._read_command(project, command_id, kind, request_hash)
        if command is None:
            return None
        revision = self._command_revision(project, command)
        payload = command.payload_json.get('use_payload')
        if not payload:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        use = ReportTemplateUse.objects.filter(project=project, command=command.command).first()
        if use is None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if (use.template_id != command.result_template_id or use.revision != command.result_revision
                or use.revision_hash != command.result_hash or use.request_hash != payload.get('request_hash')
                or str(use.draft_id) != payload.get('draft_id') or use.snapshot_hash != self._artifact_hash(use.snapshot_json)
                or use.snapshot_hash != self._artifact_hash(payload) or not self._same_json(use.snapshot_json, payload)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        expected = {
            'command_id': str(command.command),
            'draft_id': str(use.draft_id),
            'request_hash': use.request_hash,
            'template_snapshot': template_snapshot(UserTemplateSelection(revision.template_id, revision.revision, revision.revision_hash), revision),
            'template_definition': asdict(template_definition(revision)),
        }
        if not self._same_json(payload, expected) or not self._same_json(use.snapshot_json, expected):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        definition = template_definition(revision)
        return PinnedTemplateUse(expected['command_id'], expected['draft_id'], expected['request_hash'], expected['template_snapshot'], definition)

    def _command_revision(self, project, command):
        if command.result_template_id is None or command.result_revision is None or not command.result_hash:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        template = ReportTemplate.objects.filter(project=project, id=command.result_template_id).first()
        if template is None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        revision = self._revision(template, command.result_revision)
        if (revision.revision_hash != command.result_hash
                or command.payload_json.get('template_id') != revision.template_id
                or not self._same_json(command.payload_json.get('revision_payload'), self._revision_payload(revision))):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return revision

    def _refresh_usage(self, project):
        revision_bytes = sum(len(canonical_bytes(row.payload_json)) for row in ReportTemplateRevisionRecord.objects.filter(template__project=project))
        command_bytes = sum(len(canonical_bytes(row.payload_json)) for row in ReportTemplateCommand.objects.filter(project=project))
        use_bytes = sum(len(canonical_bytes(row.snapshot_json)) for row in ReportTemplateUse.objects.filter(project=project))
        total = revision_bytes + command_bytes + use_bytes
        if total > self.limits.max_project_payload_bytes:
            raise ReportError('REPORT_LIMIT')
        ReportTemplateUsage.objects.update_or_create(
            project=project,
            defaults={
                'retained_payload_bytes': total,
                'template_count': ReportTemplate.objects.filter(project=project).count(),
                'revision_count': ReportTemplateRevisionRecord.objects.filter(template__project=project).count(),
            },
        )

    def _summary(self, template):
        revision = self._revision(template, template.current_revision)
        return self._summary_from_revision(revision, template.archived)

    def _summary_from_revision(self, revision, archived):
        return TemplateSummary(revision.template_id, revision.revision, revision.revision_hash, revision.name, revision.readiness, archived)

    def _summary_payload(self, value):
        if not isinstance(value, dict):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        try:
            return TemplateSummary(**value)
        except TypeError:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _revision_payload(self, revision):
        return payload_for_revision(
            revision.template_id, revision.revision, revision.project_id,
            revision.created_by, revision.created_at, revision,
        )

    def _revision(self, template, revision):
        record = ReportTemplateRevisionRecord.objects.filter(template=template, revision=revision).first()
        if record is None:
            raise ReportError('REPORT_NOT_FOUND')
        revision_value = revision_from_payload(record.payload_json)
        if revision_value.revision_hash != record.payload_hash:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return revision_value

    def _cas(self, current, revision, revision_hash):
        if current.revision != revision or current.revision_hash != revision_hash:
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _owned(self, actor, project_id):
        try:
            return Project.objects.get(id=self._project_uuid(project_id), owner_subject=actor.subject)
        except Project.DoesNotExist:
            raise ProjectError('PROJECT_NOT_FOUND') from None

    def _lock_active(self, actor, project_id):
        identity = self._project_uuid(project_id)
        updated = Project.objects.filter(id=identity, owner_subject=actor.subject, archived=False).update(revision=F('revision') + 1)
        if updated:
            return self._owned(actor, identity)
        project = self._owned(actor, identity)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        raise ProjectError('PROJECT_NOT_FOUND')

    def _template(self, project, template_id):
        try:
            return ReportTemplate.objects.get(id=validate_uuid_text(template_id), project=project)
        except ReportTemplate.DoesNotExist:
            raise ProjectError('PROJECT_NOT_FOUND') from None

    def _selection(self, value):
        if not isinstance(value, UserTemplateSelection) or value.origin != 'user':
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        if type(value.revision) is not int or value.revision < 1:
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        return UserTemplateSelection(validate_uuid_text(value.template_id), value.revision, self._hash_text(value.revision_hash))

    def _audit(self, project, actor, kind):
        ProjectAuditEvent.objects.create(project=project, stage_id=None, kind=kind, actor_subject=actor.subject)

    def _now(self):
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ReportError('REPORT_INVALID')
        return value.astimezone(UTC).isoformat()

    def _project_uuid(self, value):
        return validate_uuid_text(str(value))

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

    def _same_json(self, left, right):
        try:
            return canonical_bytes(left) == canonical_bytes(right)
        except ArchiveError:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _hash_text(self, value):
        if type(value) is not str or len(value) != 64 or any(character not in '0123456789abcdef' for character in value):
            raise ReportError('REPORT_INVALID')
        return value
