from typing import List, Optional, Dict

from django.core.cache import caches

from .app.api.api_for_assignee_search import ApiForAssigneeSearch
from .app.api.api_for_task_hierarchy import ApiForTaskHierarchy
from .app.api.api_for_task_search import ApiForTaskSearch
from .app.domain.assignee_search_service import AssigneeSearchService
from .app.domain.convertors.task_metadata_convertor import TaskMetadataPopulator
from .app.domain.model.task import TaskSearchCriteria, MemberGroup, WorkTimeExtractorType
from .app.domain.model.config import SortingConfig
from .app.domain.task_hierarchy_service import TaskHierarchyService
from .app.domain.task_search_service import TaskSearchService
from .app.spi.task_repository import TaskRepository
from .config_loader import load_tasks_config
from .out.azure_task_repository import AzureTaskRepository
from .out.jira_task_repository import JiraTaskRepository


class TasksContainer:

    def __init__(self):
        self._config = load_tasks_config()
        self._repository_with_simple_worktime_extractor = None
        self._repositories: Dict[WorkTimeExtractorType, TaskRepository] = {}
        self._cache = None
        self._service = None
        self._hierarchy_service = None
        self._assignee_search_service = None
        self._metadata_convertor = None
        self._task_search_api = None
        self._task_hierarchy_api = None
        self._assignee_search_api = None

    @property
    def task_search_api(self) -> ApiForTaskSearch:
        if self._task_search_api is None:
            self._task_search_api = self._get_task_search_service()
        return self._task_search_api

    @property
    def task_hierarchy_api(self) -> ApiForTaskHierarchy:
        if self._task_hierarchy_api is None:
            self._task_hierarchy_api = self._get_task_hierarchy_service()
        return self._task_hierarchy_api

    @property
    def assignee_search_api(self) -> ApiForAssigneeSearch:
        if self._assignee_search_api is None:
            self._assignee_search_api = self._get_assignee_search_service()
        return self._assignee_search_api

    def get_task_repository(self, worktime_extractor_type: Optional[WorkTimeExtractorType] = None) -> TaskRepository:
        if worktime_extractor_type is None or worktime_extractor_type == WorkTimeExtractorType.SIMPLE:
            return self._get_repository_with_simple_worktime_extractor()

        if worktime_extractor_type in self._repositories:
            return self._repositories[worktime_extractor_type]

        cache = self._get_cache()
        if self._has_jira_config():
            repository = JiraTaskRepository(self._config, worktime_extractor_type, cache)
        elif self._has_azure_config():
            repository = AzureTaskRepository(self._config, worktime_extractor_type, cache)
        else:
            raise ValueError("Task data source not configured.")

        self._repositories[worktime_extractor_type] = repository
        return repository

    def _get_cache(self):
        if self._cache is None:
            self._cache = caches['task_search_results']
        return self._cache

    def _get_task_search_service(self) -> TaskSearchService:
        if self._service is None:
            self._service = TaskSearchService(
                repository=self._get_repository_with_simple_worktime_extractor(),
                task_config=self._config,
                assignee_search_service=self._get_assignee_search_service(),
                repository_factory=self.get_task_repository,
                metadata_convertor=self._get_metadata_convertor()
            )
        return self._service

    def _get_task_hierarchy_service(self) -> TaskHierarchyService:
        if self._hierarchy_service is None:
            self._hierarchy_service = TaskHierarchyService(
                repository=self._get_repository_with_simple_worktime_extractor(),
                task_config=self._config,
                assignee_search_service=self._get_assignee_search_service(),
                metadata_convertor=self._get_metadata_convertor()
            )
        return self._hierarchy_service

    def _get_assignee_search_service(self) -> AssigneeSearchService:
        if self._assignee_search_service is None:
            self._assignee_search_service = AssigneeSearchService()
        return self._assignee_search_service

    def _get_metadata_convertor(self) -> TaskMetadataPopulator:
        if self._metadata_convertor is None:
            self._metadata_convertor = TaskMetadataPopulator(self._config.workflow)
        return self._metadata_convertor

    def _get_repository_with_simple_worktime_extractor(self) -> TaskRepository:
        if self._repository_with_simple_worktime_extractor is None:
            cache = self._get_cache()
            if self._has_jira_config():
                self._repository_with_simple_worktime_extractor = JiraTaskRepository(self._config,
                                                                                     WorkTimeExtractorType.SIMPLE,
                                                                                     cache)
            elif self._has_azure_config():
                self._repository_with_simple_worktime_extractor = AzureTaskRepository(self._config,
                                                                                      WorkTimeExtractorType.SIMPLE,
                                                                                      cache)
            else:
                raise ValueError("Task data source not configured.")
        return self._repository_with_simple_worktime_extractor

    def _has_jira_config(self) -> bool:
        jira_config = self._config.jira
        return all([
            jira_config.has_authentication(),
            self._config.project.project_keys
        ])

    def _has_azure_config(self) -> bool:
        azure_config = self._config.azure
        return all([
            azure_config.azure_organization_url,
            azure_config.azure_pat,
            self._config.project.project_keys
        ])

    def create_current_tasks_search_criteria(self) -> TaskSearchCriteria:
        task_filter = self._config.task_filter
        workflow = self._config.workflow
        combined_statuses = workflow.in_progress_status_codes + workflow.pending_status_codes
        return TaskSearchCriteria(
            type_filter=task_filter.global_task_types_filter,
            status_filter=combined_statuses,
            team_filter=task_filter.global_team_filter,
        )

    def create_recently_finished_tasks_search_criteria(self) -> TaskSearchCriteria:
        from datetime import datetime, timedelta
        task_filter = self._config.task_filter
        workflow = self._config.workflow
        days_ago = datetime.now() - timedelta(days=workflow.recently_finished_tasks_days)
        now = datetime.now()
        return TaskSearchCriteria(
            type_filter=task_filter.global_task_types_filter,
            status_filter=workflow.done_status_codes,
            team_filter=task_filter.global_team_filter,
            resolution_date_range=(days_ago, now),
        )

    def create_velocity_search_criteria(self, start_date=None, end_date=None, team_id=None) -> TaskSearchCriteria:
        task_filter = self._config.task_filter
        workflow = self._config.workflow
        date_range = (start_date, end_date) if start_date and end_date else None
        return TaskSearchCriteria(
            type_filter=task_filter.global_task_types_filter,
            status_filter=workflow.done_status_codes,
            team_filter=[team_id] if team_id else task_filter.global_team_filter,
            resolution_date_range=date_range
        )

    def get_available_member_groups(self) -> List[MemberGroup]:
        member_group_ids = self._config.get_available_member_group_ids()
        return [MemberGroup(id=member_group_id, name=member_group_id) for member_group_id in member_group_ids]

    def get_member_group_config(self):
        return self._config.member_group

    def get_workflow_config(self):
        return self._config.workflow

    def get_sorting_config(self) -> SortingConfig:
        return self._config.sorting

    def is_release_field_configured(self) -> bool:
        tracker = self._config.project.task_tracker
        if tracker == 'jira':
            return bool(self._config.jira.release_field)
        if tracker == 'azure':
            return bool(self._config.azure.release_field)
        return False


tasks_container = TasksContainer()
