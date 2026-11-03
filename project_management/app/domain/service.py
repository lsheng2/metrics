from dataclasses import replace
import re

from .contracts import ProjectActor, ProjectDetail, ProjectError, ProjectSummary, ScopeSelection, StagePreview, StageSummary
from .validation import validate_actor, validate_descriptor, validate_key_name, validate_selection
from ..spi.catalog import ScopeCatalog
from ..spi.repository import ProjectRepository


class ProjectManagementService:
    def __init__(self, repository: ProjectRepository, catalog: ScopeCatalog):
        self.repository = repository
        self.catalog = catalog

    def create_project(self, actor: ProjectActor, *, key: str, name: str) -> ProjectSummary:
        validate_actor(actor)
        name = validate_key_name(key, name)
        return self.repository.create(actor, key, name)

    def list_projects(self, actor: ProjectActor, *, limit: int = 50, offset: int = 0) -> tuple[ProjectSummary, ...]:
        validate_actor(actor)
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ProjectError('INVALID_PROJECT')
        return self.repository.list(actor, limit, offset)

    def get_project(self, actor: ProjectActor, project_id: str) -> ProjectDetail:
        validate_actor(actor)
        detail = self.repository.get(actor, project_id)
        stages = tuple(replace(stage, source_status=self._source_status(stage)) for stage in detail.stages)
        return ProjectDetail(detail.project, stages)

    def preview_stage(self, actor: ProjectActor, project_id: str, *, key: str, name: str,
                      selection: ScopeSelection) -> StagePreview:
        validate_actor(actor)
        name = validate_key_name(key, name)
        validate_selection(selection)
        detail = self.repository.get(actor, project_id)
        if detail.project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        descriptor = self.catalog.resolve(selection)
        validate_descriptor(descriptor, selection)
        return StagePreview(detail.project.id, key, name, selection, descriptor, descriptor.definition_hash())

    def add_stage(self, actor: ProjectActor, project_id: str, *, key: str, name: str,
                  selection: ScopeSelection, expected_definition_hash: str | None = None) -> StageSummary:
        validate_actor(actor)
        name = validate_key_name(key, name)
        validate_selection(selection)
        detail = self.repository.get(actor, project_id)
        if detail.project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        first = self.catalog.resolve(selection)
        validate_descriptor(first, selection)
        self._check_expected_definition_hash(first, expected_definition_hash)
        second = self.catalog.resolve(selection)
        validate_descriptor(second, selection)
        if first != second:
            raise ProjectError('SOURCE_CHANGED')
        return self.repository.add_stage(actor, project_id, key, name, selection, first)

    def archive_project(self, actor: ProjectActor, project_id: str) -> ProjectSummary:
        validate_actor(actor)
        return self.repository.archive(actor, project_id)

    def _source_status(self, stage):
        try:
            descriptor = self.catalog.resolve(stage.selection)
            validate_descriptor(descriptor, stage.selection)
        except ProjectError as error:
            if error.code in {'SOURCE_UNAVAILABLE', 'INVALID_SELECTION'}:
                return 'unavailable'
            raise
        return 'current' if descriptor == stage.descriptor else 'source_changed'

    def _check_expected_definition_hash(self, descriptor, expected_definition_hash):
        if expected_definition_hash is None:
            return
        if (type(expected_definition_hash) is not str
                or not re.fullmatch(r'[0-9a-f]{64}', expected_definition_hash)
                or descriptor.definition_hash() != expected_definition_hash):
            raise ProjectError('SOURCE_CHANGED')
