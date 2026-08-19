from typing import List, Optional

from atlassian import Jira
from sd_metrics_lib.sources.jira.query import JiraSearchQueryBuilder
from sd_metrics_lib.sources.jira.tasks import JiraTaskProvider
from sd_metrics_lib.sources.jira.worklog import JiraStatusChangeWorklogExtractor
from sd_metrics_lib.sources.story_points import FunctionStoryPointExtractor
from sd_metrics_lib.sources.tasks import CachingTaskProvider
from sd_metrics_lib.utils.worktime import WorkTimeExtractor, SIMPLE_WORKTIME_EXTRACTOR, BoundarySimpleWorkTimeExtractor

from .convertors.jira import JiraTaskConverter
from .jira_server_task_provider import JiraServerTaskProvider
from .story_point_extractors import extract_jira_story_points
from ..app.domain.model.config import TasksConfig
from ..app.domain.model.task import TaskSearchCriteria, Task, EnrichmentOptions, WorkTimeExtractorType
from ..app.spi.task_repository import TaskRepository


class JiraTaskRepository(TaskRepository):

    def __init__(self, config: TasksConfig, worktime_extractor_type: Optional[WorkTimeExtractorType] = None, cache=None):
        jira_config = config.jira
        if not jira_config.has_authentication():
            raise ValueError("Missing Jira authentication configuration")

        if not config.project.project_keys:
            raise ValueError("Missing project keys configuration")

        self.jira_client = self._create_jira_client(jira_config)
        self.project_keys = config.project.project_keys
        self.jira_server_url = jira_config.jira_server_url
        self.config = config
        self.worktime_extractor_type = worktime_extractor_type or WorkTimeExtractorType.SIMPLE
        self._cache = cache

        self._story_point_extractor = FunctionStoryPointExtractor(extract_jira_story_points(config))

    @staticmethod
    def _create_jira_client(jira_config):
        if jira_config.uses_server_pat():
            return Jira(url=jira_config.jira_server_url,
                        token=jira_config.jira_api_token,
                        verify_ssl=jira_config.verify_ssl)
        return Jira(url=jira_config.jira_server_url,
                    username=jira_config.jira_email,
                    password=jira_config.jira_api_token,
                    verify_ssl=jira_config.verify_ssl,
                    cloud=True
                    )

    async def find_all(self, search_criteria: Optional[TaskSearchCriteria] = None,
                       enrichment: Optional[EnrichmentOptions] = None) -> List[Task]:
        include_time_tracking = enrichment.include_time_tracking if enrichment else True
        query = self._build_search_query(search_criteria)
        jira_tasks = await self._fetch_jira_tasks(query, include_time_tracking)
        converter = self._create_converter_for_criteria(search_criteria, enrichment)
        return [converter.convert_to_task(jira_task) for jira_task in jira_tasks]

    async def _fetch_jira_tasks(self, query: str, include_time_tracking: bool = True):
        additional_fields = ['subtasks']
        if include_time_tracking:
            additional_fields.insert(0, 'changelog')
        if self.config.jira.release_field:
            additional_fields.append(self.config.jira.release_field)
        if self.config.jira.iteration_field and self.config.jira.iteration_field not in additional_fields:
            additional_fields.append(self.config.jira.iteration_field)
        additional_fields.extend(self.config.sorting.custom_sort_field_names())

        provider_class = JiraServerTaskProvider if self.config.jira.uses_server_pat() else JiraTaskProvider
        base_provider = provider_class(
            self.jira_client,
            query,
            additional_fields=additional_fields
        )

        cached_provider = CachingTaskProvider(base_provider, self._cache)
        return cached_provider.get_tasks()

    def _build_search_query(self, search_criteria: Optional[TaskSearchCriteria]) -> str:
        if search_criteria is None:
            return JiraSearchQueryBuilder(projects=self.project_keys).build_query()

        sorted_assignees_history = None
        if search_criteria.assignees_history_filter:
            sorted_assignees_history = sorted(search_criteria.assignees_history_filter)

        sorted_assignees = None
        if search_criteria.assignee_filter:
            sorted_assignees = sorted(search_criteria.assignee_filter)

        raw_queries = None
        if search_criteria.raw_jql_filter:
            raw_queries = [search_criteria.raw_jql_filter]

        builder = JiraSearchQueryBuilder(
            projects=self.project_keys,
            task_types=search_criteria.type_filter,
            statuses=search_criteria.status_filter,
            teams=search_criteria.team_filter,
            assignees=sorted_assignees,
            assignees_history=sorted_assignees_history,
            task_ids=search_criteria.id_filter,
            last_modified_dates=search_criteria.resolved_state_change_date_range(),
            resolution_dates=search_criteria.resolution_date_range,
            raw_queries=raw_queries
        )

        return builder.build_query()

    def _create_converter_for_criteria(self, criteria: Optional[TaskSearchCriteria],
                                       enrichment: Optional[EnrichmentOptions] = None) -> JiraTaskConverter:
        include_time_tracking = enrichment.include_time_tracking if enrichment else True
        worktime_extractor = self._create_worktime_extractor_from_criteria(criteria)

        worklog_statuses = self._resolve_transition_statuses(self.config)
        if enrichment and enrichment.worklog_transition_statuses:
            worklog_statuses = enrichment.worklog_transition_statuses

        worklog_extractor = JiraStatusChangeWorklogExtractor(
            transition_statuses=worklog_statuses,
            worktime_extractor=worktime_extractor
        )

        return JiraTaskConverter(self.config, worklog_extractor, self._story_point_extractor, include_time_tracking)

    def _create_worktime_extractor_from_criteria(self, criteria: Optional[TaskSearchCriteria]) -> WorkTimeExtractor:
        if self.worktime_extractor_type == WorkTimeExtractorType.BOUNDARY_FROM_LAST_MODIFIED:
            if criteria:
                start_date, end_date = criteria.resolved_state_change_date_range() or (None, None)
                if start_date and end_date:
                    return BoundarySimpleWorkTimeExtractor(start_date, end_date)

        elif self.worktime_extractor_type == WorkTimeExtractorType.BOUNDARY_FROM_RESOLUTION:
            if criteria and criteria.resolution_date_range:
                start_date, end_date = criteria.resolution_date_range
                if start_date and end_date:
                    return BoundarySimpleWorkTimeExtractor(start_date, end_date)

        return SIMPLE_WORKTIME_EXTRACTOR

    @staticmethod
    def _resolve_transition_statuses(config: TasksConfig) -> List[str]:
        all_statuses = []
        for stage_name, statuses in config.workflow.stages.items():
            all_statuses.extend(statuses)
        return all_statuses
