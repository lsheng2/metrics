from typing import Dict, Optional, List

from sd_metrics_lib.utils.time import TimeUnit

from velocity.app.domain.model.config import MemberVelocityConfig
from velocity.app.domain.model.velocity import ReportGenerationParameters, ReportType, TaskFilter
from ..convertors.velocity_chart_convertor import VelocityChartConvertor
from ..convertors.velocity_report_convertor import VelocityReportConvertor
from ..data.chart_data import ChartData
from ..data.velocity_report_data import VelocityReportData
from ..data.velocity_threshold_data import VelocityThresholdsData, VelocityLevelThreshold
from ..utils.chart_transform_utils import ChartTransformUtils


class DevVelocityFacade:
    def __init__(self, velocity_api, assignee_search_api,
                 available_member_groups,
                 velocity_chart_convertor: VelocityChartConvertor,
                 velocity_report_convertor: VelocityReportConvertor,
                 member_velocity_config: MemberVelocityConfig,
                 ideal_hours_per_day: float,
                 member_group_custom_filters: Optional[Dict[str, str]] = None,
                 development_stage_status_codes: Optional[List[str]] = None):
        self._velocity_api = velocity_api
        self._assignee_search_api = assignee_search_api
        self._available_member_groups = available_member_groups
        self._velocity_chart_convertor = velocity_chart_convertor
        self._velocity_report_convertor = velocity_report_convertor
        self._member_velocity_config = member_velocity_config
        self._ideal_hours_per_day = ideal_hours_per_day
        self._member_group_custom_filters = member_group_custom_filters
        self._development_stage_status_codes = development_stage_status_codes

    def has_custom_filter(self, member_group_id: Optional[str]) -> bool:
        if not member_group_id or not self._member_group_custom_filters:
            return False
        return member_group_id in self._member_group_custom_filters

    async def get_velocity_reports_data(self, member_group_id: Optional[str] = None,
                                         number_of_periods: int = 6,
                                         include_all_statuses: bool = False,
                                         use_custom_filter: bool = False) -> List[VelocityReportData]:
        custom_query = self._resolve_custom_query(member_group_id) if use_custom_filter else None
        velocity_reports = await self._get_velocity_reports(member_group_id, number_of_periods, include_all_statuses, custom_query)
        return self._velocity_report_convertor.convert_velocity_reports_to_data_with_names(velocity_reports)

    def get_velocity_chart_data(self, velocity_reports_data: List[VelocityReportData],
                                rolling_avg_window: int = 0,
                                display_periods: int = 0) -> Optional[ChartData]:
        chart = self._velocity_chart_convertor.convert_dev_velocity_reports_to_velocity_chart(velocity_reports_data)
        if rolling_avg_window > 0 and chart:
            chart = ChartTransformUtils.apply_rolling_average(chart, rolling_avg_window)
        if display_periods > 0 and chart:
            chart = ChartTransformUtils.trim_to_last_n_periods(chart, display_periods)
        return chart

    def get_story_points_chart_data(self, velocity_reports_data: List[VelocityReportData],
                                    rolling_avg_window: int = 0,
                                    display_periods: int = 0) -> Optional[ChartData]:
        chart = self._velocity_chart_convertor.convert_dev_velocity_reports_to_story_points_chart(velocity_reports_data)
        if rolling_avg_window > 0 and chart:
            chart = ChartTransformUtils.apply_rolling_average(chart, rolling_avg_window)
        if display_periods > 0 and chart:
            chart = ChartTransformUtils.trim_to_last_n_periods(chart, display_periods)
        return chart

    def get_velocity_thresholds(self) -> VelocityThresholdsData:
        thresholds = []
        for level_name, multiplier in self._member_velocity_config.seniority_levels.items():
            threshold = self._ideal_hours_per_day / (self._member_velocity_config.story_points_to_ideal_hours_ratio * multiplier)
            thresholds.append(VelocityLevelThreshold(level_name, threshold))

        thresholds.sort(key=lambda t: t.threshold)
        return VelocityThresholdsData(thresholds)

    def _resolve_custom_query(self, member_group_id: Optional[str]) -> Optional[str]:
        if not member_group_id or not self._member_group_custom_filters:
            return None
        return self._member_group_custom_filters.get(member_group_id)

    async def _get_velocity_reports(self, member_group_id: Optional[str],
                                    number_of_periods: int = 6,
                                    include_all_statuses: bool = False,
                                    custom_query: Optional[str] = None):
        criteria = ReportGenerationParameters(
            time_unit=TimeUnit.MONTH,
            number_of_periods=number_of_periods,
            report_type=ReportType.MEMBER_SCOPE,
            scope_id=member_group_id,
            task_filter=TaskFilter(include_all_statuses=include_all_statuses, custom_query=custom_query,
                                  worklog_transition_statuses=self._development_stage_status_codes)
        )
        return await self._velocity_api.generate_velocity_report(criteria)
