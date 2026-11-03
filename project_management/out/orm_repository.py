from contextlib import contextmanager
from dataclasses import asdict

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F

from project_management.app.domain.contracts import (
    ProjectDetail, ProjectError, ProjectSummary, ScopeDescriptor, ScopeSelection, StageSummary,
)
from project_management.app.domain.validation import project_uuid
from project_management.models import Project, ProjectAuditEvent, ProjectStage


@contextmanager
def storage_errors():
    try:
        yield
    except OperationalError as error:
        if 'locked' in str(error).lower() or 'busy' in str(error).lower():
            raise ProjectError('PROJECT_BUSY') from None
        raise


class OrmProjectRepository:
    def create(self, actor, key, name):
        with storage_errors():
            try:
                with transaction.atomic():
                    project, created = Project.objects.get_or_create(
                        owner_subject=actor.subject, key=key, defaults={'name': name},
                    )
                    if project.name != name:
                        raise ProjectError('PROJECT_KEY_CONFLICT')
                    if created:
                        self._audit(project, actor, 'project_created')
                    return self._project(project)
            except IntegrityError:
                project = Project.objects.get(owner_subject=actor.subject, key=key)
                if project.name != name:
                    raise ProjectError('PROJECT_KEY_CONFLICT') from None
                return self._project(project)

    def list(self, actor, limit, offset):
        with storage_errors():
            return tuple(self._project(row) for row in Project.objects.filter(
                owner_subject=actor.subject,
            )[offset:offset + limit])

    def get(self, actor, project_id):
        with storage_errors():
            project = self._owned(actor, project_id)
            return ProjectDetail(self._project(project), tuple(self._stage(row) for row in project.stages.all()[:100]))

    def add_stage(self, actor, project_id, key, name, selection, descriptor):
        with storage_errors(), transaction.atomic():
            project = self._lock_owned(actor, project_id)
            if project.archived:
                raise ProjectError('PROJECT_ARCHIVED')
            existing = project.stages.filter(key=key).first()
            if existing:
                if (existing.name != name or existing.selection_json != asdict(selection)
                        or existing.descriptor_json != asdict(descriptor)):
                    raise ProjectError('STAGE_RULE_IMMUTABLE')
                return self._stage(existing, 'current')
            if project.stages.count() >= 100:
                raise ProjectError('PROJECT_LIMIT')
            stage = ProjectStage.objects.create(
                project=project, key=key, name=name, selection_json=asdict(selection),
                descriptor_json=asdict(descriptor), definition_hash=descriptor.definition_hash(),
            )
            self._audit(project, actor, 'stage_created', stage.id)
            return self._stage(stage, 'current')

    def archive(self, actor, project_id):
        with storage_errors(), transaction.atomic():
            project = self._lock_owned(actor, project_id)
            if not project.archived:
                project.archived = True
                project.save(update_fields=['archived'])
                self._audit(project, actor, 'project_archived')
            return self._project(project)

    def _owned(self, actor, project_id):
        try:
            return Project.objects.get(id=project_uuid(project_id), owner_subject=actor.subject)
        except Project.DoesNotExist:
            raise ProjectError('PROJECT_NOT_FOUND') from None

    def _lock_owned(self, actor, project_id):
        identity = project_uuid(project_id)
        updated = Project.objects.filter(id=identity, owner_subject=actor.subject).update(revision=F('revision') + 1)
        if not updated:
            raise ProjectError('PROJECT_NOT_FOUND')
        return self._owned(actor, identity)

    def _audit(self, project, actor, kind, stage_id=None):
        ProjectAuditEvent.objects.create(
            project=project, stage_id=stage_id, kind=kind, actor_subject=actor.subject,
        )

    def _project(self, row):
        return ProjectSummary(str(row.id), row.key, row.name, row.archived, row.created_at)

    def _stage(self, row, source_status='unchecked'):
        descriptor = ScopeDescriptor(**row.descriptor_json)
        if descriptor.definition_hash() != row.definition_hash:
            raise ValueError('Stored stage integrity validation failed.')
        return StageSummary(
            str(row.id), row.key, row.name, ScopeSelection(**row.selection_json),
            descriptor, row.definition_hash, row.created_at, source_status,
        )
