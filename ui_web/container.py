from django.conf import settings
from sd_metrics_lib.utils.time import TimePolicy

from forecast.container import forecast_container
from pull_requests.container import pull_requests_container
from tasks.app.domain.model.config import SortingConfig
from tasks.container import tasks_container
from velocity.container import velocity_container
from bug_metrics.container import bug_metrics_container
from jira_sync.container import jira_sync_container
from .convertors.member_convertor import MemberConvertor
from .convertors.pull_request_convertor import PullRequestConvertor
from .convertors.task_convertor import TaskConvertor
from .convertors.task_forecast_chart_convertor import TaskForecastChartConvertor
from .convertors.task_forecast_convertor import TaskForecastConvertor
from .convertors.velocity_chart_convertor import VelocityChartConvertor
from .convertors.developer_velocity_summary_convertor import DeveloperVelocitySummaryConvertor
from .convertors.velocity_report_convertor import VelocityReportConvertor
from .convertors.velocity_task_detail_convertor import VelocityTaskDetailConvertor
from .facades.child_tasks_facade import ChildTasksFacade
from .facades.dev_velocity_facade import DevVelocityFacade
from .facades.tasks_velocity_facade import TasksVelocityFacade
from .facades.members_facade import MembersFacade
from .facades.task_forecast_facade import TaskForecastFacade
from .facades.task_filter_facade import TaskFilterFacade
from .facades.pull_requests_facade import PullRequestsFacade
from .facades.bug_trend_facade import BugTrendFacade
from .facades.data_health_facade import DataHealthFacade
from .facades.tasks_facade import TasksFacade
from .facades.team_velocity_facade import TeamVelocityFacade
from .utils.available_member_stage_filter import AvailableMemberStageFilter
from .utils.federated_data_post_processors import MemberGroupTaskFilter
from .utils.filter_fields import build_field_filters


class UiWebContainer:
    def __init__(self):
        self._task_convertor = None
        self._forecast_task_convertor = None
        self._member_convertor = None
        self._task_forecast_convertor = None
        self._velocity_chart_convertor = None
        self._velocity_report_convertor = None
        self._velocity_task_detail_convertor = None
        self._task_forecast_chart_convertor = None

        self._tasks_facade = None
        self._task_filter_facade = None
        self._child_tasks_facade = None
        self._members_facade = None
        self._team_velocity_facade = None
        self._dev_velocity_facade = None
        self._tasks_velocity_facade = None
        self._developer_velocity_summary_convertor = None
        self._task_forecast_facade = None
        self._member_group_task_filter = None
        self._pull_request_convertor = None
        self._pull_requests_facade = None
        self._bug_trend_facade = None
        self._data_health_facade = None

    @property
    def task_convertor(self) -> TaskConvertor:
        if self._task_convertor is None:
            self._task_convertor = TaskConvertor(velocity_container.ideal_time_policy)
        return self._task_convertor

    @property
    def forecast_task_convertor(self) -> TaskConvertor:
        if self._forecast_task_convertor is None:
            self._forecast_task_convertor = TaskConvertor(TimePolicy.BUSINESS_HOURS)
        return self._forecast_task_convertor

    @property
    def member_convertor(self) -> MemberConvertor:
        if self._member_convertor is None:
            self._member_convertor = MemberConvertor()
        return self._member_convertor


    @property
    def task_forecast_convertor(self) -> TaskForecastConvertor:
        if self._task_forecast_convertor is None:
            self._task_forecast_convertor = TaskForecastConvertor()
        return self._task_forecast_convertor

    @property
    def pull_request_convertor(self) -> PullRequestConvertor:
        if self._pull_request_convertor is None:
            self._pull_request_convertor = PullRequestConvertor()
        return self._pull_request_convertor

    @property
    def pull_requests_facade(self) -> PullRequestsFacade:
        if self._pull_requests_facade is None:
            enabled = pull_requests_container.is_supported()
            self._pull_requests_facade = PullRequestsFacade(
                pull_request_search_api=pull_requests_container.pull_request_search_api if enabled else None,
                task_search_api=tasks_container.task_search_api,
                pull_request_convertor=self.pull_request_convertor,
                sorting_config=self._pull_request_sorting_config(),
                members=tasks_container.get_member_group_config().members,
                enabled=enabled
            )
        return self._pull_requests_facade

    @property
    def bug_trend_facade(self) -> BugTrendFacade:
        if self._bug_trend_facade is None:
            self._bug_trend_facade = BugTrendFacade(
                bug_metrics_container.bug_trend_api,
                jira_sync_container.scope_metadata_api,
            )
        return self._bug_trend_facade

    @property
    def data_health_facade(self) -> DataHealthFacade:
        if self._data_health_facade is None:
            self._data_health_facade = DataHealthFacade(
                jira_sync_container.jira_sync_api,
                bug_metrics_container.bug_trend_api
            )
        return self._data_health_facade

    @staticmethod
    def _pull_request_sorting_config() -> SortingConfig:
        return SortingConfig(
            stage_sort_overrides={},
            default_sort_criteria=tasks_container.get_sorting_config().default_sort_criteria
        )

    @property
    def tasks_facade(self) -> TasksFacade:
        if self._tasks_facade is None:
            self._tasks_facade = TasksFacade(
                task_search_api=tasks_container.task_search_api,
                forecast_api=forecast_container.forecast_api,
                task_convertor=self.task_convertor,
                available_member_groups=tasks_container.get_available_member_groups(),
                current_tasks_search_criteria=tasks_container.create_current_tasks_search_criteria(),
                recently_finished_tasks_search_criteria=tasks_container.create_recently_finished_tasks_search_criteria(),
                workflow_config=tasks_container.get_workflow_config(),
                member_group_task_filter=self._get_member_group_task_filter(),
                member_convertor=self.member_convertor,
                member_group_custom_filters=tasks_container.get_member_group_config().custom_filters,
                merge_unassigned_into_filtered_group=tasks_container.get_member_group_config().merge_unassigned_into_filtered_group,
                release_column_enabled=tasks_container.is_release_field_configured(),
                lazy_loading_enabled=settings.METRICS_CURRENT_TASKS_LAZY_LOADING,
                pull_request_search_api=self._pull_request_search_api_if_supported()
            )
        return self._tasks_facade

    @staticmethod
    def _pull_request_search_api_if_supported():
        return pull_requests_container.pull_request_search_api if pull_requests_container.is_supported() else None

    @property
    def task_filter_facade(self) -> TaskFilterFacade:
        if self._task_filter_facade is None:
            self._task_filter_facade = TaskFilterFacade(
                build_field_filters(settings.METRICS_TASK_FILTER_FIELDS)
            )
        return self._task_filter_facade

    @property
    def child_tasks_facade(self) -> ChildTasksFacade:
        if self._child_tasks_facade is None:
            self._child_tasks_facade = ChildTasksFacade(
                tasks_container.task_search_api,
                forecast_container.forecast_api,
                self.task_convertor,
                pull_request_search_api=self._pull_request_search_api_if_supported()
            )
        return self._child_tasks_facade

    @property
    def members_facade(self) -> MembersFacade:
        if self._members_facade is None:
            self._members_facade = MembersFacade(
                tasks_container.task_search_api,
                self.member_convertor,
                self._get_available_member_stage_filter()
            )
        return self._members_facade

    @staticmethod
    def _get_available_member_stage_filter() -> AvailableMemberStageFilter:
        return AvailableMemberStageFilter(
            tasks_container.get_member_group_config(),
            settings.METRICS_AVAILABLE_MEMBER_STAGES_FILTER
        )

    @property
    def team_velocity_facade(self) -> TeamVelocityFacade:
        if self._team_velocity_facade is None:
            self._team_velocity_facade = TeamVelocityFacade(
                velocity_container.velocity_report_generation_api,
                tasks_container.assignee_search_api,
                tasks_container.get_available_member_groups(),
                self.member_convertor,
                self._get_velocity_chart_convertor(),
                self._get_velocity_report_convertor(),
                tasks_container.get_member_group_config().custom_filters
            )
        return self._team_velocity_facade

    @property
    def dev_velocity_facade(self) -> DevVelocityFacade:
        if self._dev_velocity_facade is None:
            self._dev_velocity_facade = DevVelocityFacade(
                velocity_api=velocity_container.velocity_report_generation_api,
                assignee_search_api=tasks_container.assignee_search_api,
                available_member_groups=tasks_container.get_available_member_groups(),
                velocity_chart_convertor=self._get_velocity_chart_convertor(),
                velocity_report_convertor=self._get_velocity_report_convertor(),
                member_velocity_config=velocity_container.get_member_velocity_config(),
                ideal_hours_per_day=velocity_container.ideal_time_policy.hours_per_day,
                member_group_custom_filters=tasks_container.get_member_group_config().custom_filters,
                development_stage_status_codes=tasks_container.get_workflow_config().stages.get("Development", [])
            )
        return self._dev_velocity_facade

    @property
    def tasks_velocity_facade(self) -> TasksVelocityFacade:
        if self._tasks_velocity_facade is None:
            self._tasks_velocity_facade = TasksVelocityFacade(
                task_search_api=tasks_container.task_search_api,
                create_velocity_search_criteria=tasks_container.create_velocity_search_criteria,
                resolve_member_group_members=velocity_container.resolve_member_group_members,
                velocity_task_detail_convertor=self._get_velocity_task_detail_convertor(),
                velocity_calculation_api=velocity_container.velocity_calculation_api,
                in_progress_status_codes=tasks_container.get_workflow_config().in_progress_status_codes,
                development_stage_status_codes=tasks_container.get_workflow_config().stages.get("Development", []),
                member_group_custom_filters=tasks_container.get_member_group_config().custom_filters
            )
        return self._tasks_velocity_facade

    @property
    def developer_velocity_summary_convertor(self) -> DeveloperVelocitySummaryConvertor:
        if self._developer_velocity_summary_convertor is None:
            self._developer_velocity_summary_convertor = DeveloperVelocitySummaryConvertor(
                working_days_per_month=velocity_container.ideal_time_policy.days_per_month
            )
        return self._developer_velocity_summary_convertor

    @property
    def task_forecast_facade(self) -> TaskForecastFacade:
        if self._task_forecast_facade is None:
            self._task_forecast_facade = TaskForecastFacade(
                forecast_container.forecast_api,
                self.task_forecast_convertor,
                self.forecast_task_convertor,
                self._get_task_forecast_chart_convertor()
            )
        return self._task_forecast_facade

    def _get_member_group_task_filter(self) -> MemberGroupTaskFilter:
        if self._member_group_task_filter is None:
            self._member_group_task_filter = MemberGroupTaskFilter(tasks_container.get_member_group_config())
        return self._member_group_task_filter

    def _get_velocity_task_detail_convertor(self) -> VelocityTaskDetailConvertor:
        if self._velocity_task_detail_convertor is None:
            self._velocity_task_detail_convertor = VelocityTaskDetailConvertor(
                time_policy=velocity_container.ideal_time_policy
            )
        return self._velocity_task_detail_convertor

    def _get_velocity_chart_convertor(self) -> VelocityChartConvertor:
        if self._velocity_chart_convertor is None:
            self._velocity_chart_convertor = VelocityChartConvertor()
        return self._velocity_chart_convertor

    def _get_velocity_report_convertor(self) -> VelocityReportConvertor:
        if self._velocity_report_convertor is None:
            self._velocity_report_convertor = VelocityReportConvertor(tasks_container.assignee_search_api)
        return self._velocity_report_convertor

    def _get_task_forecast_chart_convertor(self) -> TaskForecastChartConvertor:
        if self._task_forecast_chart_convertor is None:
            self._task_forecast_chart_convertor = TaskForecastChartConvertor()
        return self._task_forecast_chart_convertor


ui_web_container = UiWebContainer()
