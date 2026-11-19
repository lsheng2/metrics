import asyncio
import calendar
import json
from dataclasses import asdict
from datetime import datetime, time, timezone

from ..container import ui_web_container
from ..data.hierarchical_item_data import HierarchicalItemData
from ..utils.chart_json_utils import ChartJsonUtils
from ..utils.chart_transform_utils import ChartTransformUtils
from ..utils.developer_series_utils import DeveloperSeriesUtils
from ..utils.task_grouping_utils import TaskGroupingUtils
from ..utils.velocity_sort_utils import VelocitySortUtils
from .graceful_template_view import GracefulTemplateView

DISPLAY_PERIODS = 6


def chronological_chart_json(chart, last_periods: int = 0):
    """Chart.js JSON in month order, or None when there is nothing to plot."""
    if not chart or not chart.labels:
        return None
    VelocitySortUtils.sort_chart_data_chronologically(chart)
    if last_periods:
        chart = ChartTransformUtils.trim_to_last_n_periods(chart, last_periods)
    return ChartJsonUtils.convert_chart_data_to_chartjs_json(chart)


class DevVelocityView(GracefulTemplateView):
    template_name = 'dev_velocity.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dev_velocity_facade = ui_web_container.dev_velocity_facade

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ["partials/dev_velocity_content.html"]
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        team_id = kwargs.get('team_id')
        member_group_id = team_id or self.request.GET.get('member_group_id')
        rolling_avg = int(self.request.GET.get('rolling_avg', 0))
        include_all_statuses = self.request.GET.get('all_tasks') == 'true'
        use_custom_filter = self.request.GET.get('use_custom_filter') == 'true'

        context["month_velocity"] = None
        context["month_sp"] = None
        context["developer_series"] = []
        context["success"] = False
        context["build_page_title"] = 'Developer Velocity Dashboard'
        context["velocity_rolling_avg"] = rolling_avg
        context["member_group_id"] = member_group_id or ''
        context["include_all_statuses"] = include_all_statuses
        context["use_custom_filter"] = use_custom_filter
        context["has_custom_filter"] = self.dev_velocity_facade.has_custom_filter(member_group_id)
        context["selected_period"] = self.request.GET.get('period', '')
        context["selected_developers"] = self.request.GET.get('developers', '')

        velocity_thresholds = self.dev_velocity_facade.get_velocity_thresholds()
        context["velocity_thresholds"] = json.dumps(asdict(velocity_thresholds))

        extra_periods = rolling_avg - 1 if rolling_avg > 0 else 0
        velocity_reports_data = asyncio.run(
            self.dev_velocity_facade.get_velocity_reports_data(
                member_group_id, DISPLAY_PERIODS + extra_periods, include_all_statuses, use_custom_filter
            )
        )

        trim_periods = DISPLAY_PERIODS if rolling_avg > 0 else 0
        velocity_chart = self.dev_velocity_facade.get_velocity_chart_data(
            velocity_reports_data, rolling_avg, trim_periods
        )
        story_points_chart = self.dev_velocity_facade.get_story_points_chart_data(
            velocity_reports_data, rolling_avg, trim_periods
        )

        context["developer_series"] = DeveloperSeriesUtils.from_chart(velocity_chart, context["selected_developers"])
        context["month_velocity"] = chronological_chart_json(velocity_chart)
        context["month_sp"] = chronological_chart_json(story_points_chart)
        context["success"] = True


class BaseVelocityTasksView(GracefulTemplateView):
    template_name = 'partials/dev_velocity_tasks.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tasks_velocity_facade = ui_web_container.tasks_velocity_facade
        self.summary_convertor = ui_web_container.developer_velocity_summary_convertor

    def _build_task_hierarchy(self, velocity_tasks, period):
        if not velocity_tasks:
            return []
        developer_groups = self._group_by_developer(velocity_tasks)
        total_count = sum(g.count for g in developer_groups)
        return [HierarchicalItemData(
            name=f"Tasks — {period}",
            type="member_group",
            count=total_count,
            items=developer_groups
        )]

    def _group_by_developer(self, velocity_tasks):
        groups = TaskGroupingUtils.group_tasks_by_key(
            velocity_tasks,
            key_extractor=lambda t: t.assignment.assignee.display_name,
            group_type="task_velocity"
        )
        return self.summary_convertor.enrich_with_summaries(groups)

    @staticmethod
    def _parse_month_period(period: str):
        year, month = int(period[:4]), int(period[5:7])
        last_day = calendar.monthrange(year, month)[1]
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        end_date = datetime.combine(datetime(year, month, last_day), time.max, tzinfo=timezone.utc)
        return start_date, end_date


class DevVelocityTasksView(BaseVelocityTasksView):

    def populate_context(self, context, **kwargs):
        context["task_groups"] = []

        developer_names, period, member_group_id, include_all_statuses, use_custom_filter = self._parse_request_params()
        developer_names = self.tasks_velocity_facade.resolve_developer_names(developer_names, member_group_id)

        start_date, end_date = self._parse_month_period(period)
        velocity_tasks = asyncio.run(
            self.tasks_velocity_facade.get_tasks(
                developer_names, start_date, end_date, member_group_id, include_all_statuses, use_custom_filter
            )
        )
        context["task_groups"] = self._build_task_hierarchy(velocity_tasks, period)

    def _parse_request_params(self):
        period = self.request.GET.get('period', '')
        member_group_id = self.request.GET.get('member_group_id')
        include_all_statuses = self.request.GET.get('all_tasks') == 'true'
        use_custom_filter = self.request.GET.get('use_custom_filter') == 'true'

        developers_param = self.request.GET.get('developers', '')
        developer_names = [d.strip() for d in developers_param.split(',') if d.strip()]

        return developer_names, period, member_group_id, include_all_statuses, use_custom_filter
