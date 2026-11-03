from project_management.app.domain.contracts import (
    ProjectActor, ProjectDetail, ProjectError, ProjectSummary, ScopeDescriptor, ScopeSelection,
    StagePreview, StageSummary,
)
from project_management.app.domain.service import ProjectManagementService
from project_management.out.orm_repository import OrmProjectRepository


class ApiForProjectManagement(ProjectManagementService):
    def __init__(self, catalog):
        super().__init__(OrmProjectRepository(), catalog)


__all__ = ['ApiForProjectManagement', 'ProjectActor', 'ProjectDetail', 'ProjectError', 'ProjectSummary',
           'ScopeDescriptor', 'ScopeSelection', 'StagePreview', 'StageSummary']
