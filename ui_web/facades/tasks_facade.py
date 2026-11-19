import asyncio
from copy import deepcopy
from typing import List, Optional, Dict

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import Task, EnrichmentOptions, TaskSearchCriteria, MemberGroup
from tasks.out.convertors.task_conversion_utils import TaskConversionUtils
from ..convertors.member_convertor import MemberConvertor
from ..convertors.task_convertor import TaskConvertor
from ..data.member_data import MemberGroupData
from ..data.task_data import TaskData
from ..utils.federated_data_fetcher import FederatedDataFetcher
from ..utils.federated_data_post_processors import MemberGroupTaskFilter
from ..utils.forecast_population_utils import ForecastPopulationUtils
from ..utils.pull_request_gateway_lookup_utils import PullRequestGatewayLookupUtils


class TasksFacade:

    def __init__(self, task_search_api, forecast_api, task_convertor: TaskConvertor,
                 available_member_groups: List[MemberGroup],
                 current_tasks_search_criteria: TaskSearchCriteria,
                 recently_finished_tasks_search_criteria: TaskSearchCriteria,
                 workflow_config: WorkflowConfig,
                 member_group_task_filter: MemberGroupTaskFilter,
                 member_convertor: MemberConvertor,
                 member_group_custom_filters: Optional[Dict[str, str]] = None,
                 merge_unassigned_into_filtered_group: bool = False,
                 release_column_enabled: bool = False,
                 lazy_loading_enabled: bool = True,
                 pull_request_search_api=None):
        self.task_search_api = task_search_api
        self.forecast_api = forecast_api
        self.available_member_groups = available_member_groups
        self.__current_tasks_search_criteria_template = current_tasks_search_criteria
        self.__recently_finished_tasks_search_criteria_template = recently_finished_tasks_search_criteria
        self.workflow_config = workflow_config
        self.member_group_task_filter = member_group_task_filter
        self.task_convertor = task_convertor
        self.member_convertor = member_convertor
        self.member_group_custom_filters = member_group_custom_filters
        self.merge_unassigned_into_filtered_group = merge_unassigned_into_filtered_group
        self._release_column_enabled = release_column_enabled
        self._lazy_loading_enabled = lazy_loading_enabled
        self.pull_request_search_api = pull_request_search_api

    async def get_tasks(self, member_group_id: Optional[str] = None) -> List[TaskData]:
        tasks = await self._fetch_tasks(member_group_id, self._build_full_enrichment())
        await self._enrich_forecast(tasks)
        tasks_data = self._convert_to_task_data(tasks)
        await self._enrich_linked_pull_requests(tasks_data)
        return tasks_data

    async def get_task_structure(self, member_group_id: Optional[str] = None) -> List[TaskData]:
        tasks = await self._fetch_tasks(member_group_id, self._build_structural_enrichment())
        return self._convert_to_task_data(tasks)

    async def get_tasks_by_ids(self, task_ids: List[str]) -> List[TaskData]:
        if not task_ids:
            return []
        tasks = await self.task_search_api.search(TaskSearchCriteria(id_filter=task_ids), self._build_full_enrichment())
        await self._enrich_forecast(tasks)
        tasks_data = self._convert_to_task_data(tasks)
        await self._enrich_linked_pull_requests(tasks_data)
        return tasks_data

    def get_available_member_groups(self) -> List[MemberGroupData]:
        return [self.member_convertor.convert_member_group_to_data(group) for group in
                self.available_member_groups]

    def is_release_column_enabled(self) -> bool:
        return self._release_column_enabled

    def is_lazy_loading_enabled(self) -> bool:
        return self._lazy_loading_enabled

    def is_pull_request_gateway_column_enabled(self) -> bool:
        return self.pull_request_search_api is not None

    def task_table_colspan(self) -> int:
        colspan = 8
        if self._release_column_enabled:
            colspan += 1
        if self.is_pull_request_gateway_column_enabled():
            colspan += 1
        return colspan

    def _convert_to_task_data(self, tasks: List[Task]) -> List[TaskData]:
        return [self.task_convertor.convert_task_to_data(task) for task in tasks]

    async def _fetch_tasks(self, member_group_id: Optional[str], enrichment: EnrichmentOptions) -> List[Task]:
        current_tasks_future = self._build_task_fetcher(
            lambda: self.task_search_api.search(self._create_current_tasks_search_criteria(member_group_id), enrichment),
            member_group_id
        )
        recently_finished_tasks_future = self._build_task_fetcher(
            lambda: self.task_search_api.search(self._create_recently_finished_tasks_search_criteria(member_group_id), enrichment),
            member_group_id
        )

        current_tasks, recently_finished_tasks = await asyncio.gather(
            current_tasks_future, recently_finished_tasks_future
        )

        all_tasks = current_tasks + recently_finished_tasks

        self._relabel_unassigned_tasks(all_tasks, member_group_id)

        return all_tasks

    def _build_task_fetcher(self, task_fetcher_func, member_group_id: Optional[str]):
        return (
            FederatedDataFetcher
            .for_(task_fetcher_func)
            .with_result_post_processor(
                lambda all_tasks: self.member_group_task_filter.filter(all_tasks, member_group_id)
            )
            .fetch()
        )

    async def _enrich_forecast(self, tasks: List[Task]) -> None:
        await ForecastPopulationUtils.populate_ideal_forecasts_batch(tasks, self.forecast_api)

    async def _enrich_linked_pull_requests(self, tasks_data: List[TaskData]) -> None:
        await PullRequestGatewayLookupUtils.populate_linked_pull_requests(tasks_data, self.pull_request_search_api)

    def _build_full_enrichment(self) -> EnrichmentOptions:
        return self._build_enrichment(include_time_tracking=True)

    def _build_structural_enrichment(self) -> EnrichmentOptions:
        return self._build_enrichment(include_time_tracking=False)

    def _build_enrichment(self, include_time_tracking: bool) -> EnrichmentOptions:
        return EnrichmentOptions(
            include_time_tracking=include_time_tracking,
            worklog_transition_statuses=self.workflow_config.in_progress_status_codes
        )

    def _create_current_tasks_search_criteria(self, member_group_id: Optional[str]):
        criteria = deepcopy(self.__current_tasks_search_criteria_template)
        self._apply_member_group_custom_filter(criteria, member_group_id)
        return criteria

    def _create_recently_finished_tasks_search_criteria(self, member_group_id: Optional[str]):
        criteria = deepcopy(self.__recently_finished_tasks_search_criteria_template)
        self._apply_member_group_custom_filter(criteria, member_group_id)
        return criteria

    def _relabel_unassigned_tasks(self, tasks: List[Task], member_group_id: Optional[str]):
        if not member_group_id or not self.merge_unassigned_into_filtered_group:
            return

        for task in tasks:
            if task.assignment.member_group and task.assignment.member_group.name == TaskConversionUtils.UNASSIGNED_MEMBER_GROUP_NAME:
                task.assignment.member_group = MemberGroup(id=member_group_id, name=member_group_id)

    def _apply_member_group_custom_filter(self, criteria: TaskSearchCriteria, member_group_id: Optional[str]):
        if member_group_id and self.member_group_custom_filters:
            custom_filter = self.member_group_custom_filters.get(member_group_id)
            if custom_filter:
                criteria.raw_jql_filter = custom_filter
