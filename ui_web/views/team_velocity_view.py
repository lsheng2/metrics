import asyncio

from ..container import ui_web_container
from ..utils.velocity_summary_utils import VelocitySummaryUtils
from .dev_velocity_view import BaseVelocityTasksView, chronological_chart_json
from .graceful_template_view import GracefulTemplateView

DISPLAY_PERIODS = 12


class TeamVelocityView(GracefulTemplateView):
    template_name = 'team_velocity.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.team_velocity_facade = ui_web_container.team_velocity_facade

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ["partials/team_velocity_content.html"]
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        team_id = kwargs.get('team_id')
        member_group_id = team_id or self.request.GET.get('member_group_id')
        rolling_avg = int(self.request.GET.get('rolling_avg', 0))
        use_custom_filter = self.request.GET.get('use_custom_filter') == 'true'

        context["month_velocity"] = None
        context["month_sp"] = None
        context["velocity_summary"] = None
        context["success"] = False
        context["build_page_title"] = 'Team Velocity Dashboard'
        context["velocity_rolling_avg"] = rolling_avg
        context["member_group_id"] = member_group_id or ''
        context["use_custom_filter"] = use_custom_filter
        context["has_custom_filter"] = self.team_velocity_facade.has_custom_filter(member_group_id)
        context["selected_period"] = self.request.GET.get('period', '')

        extra_periods = rolling_avg - 1 if rolling_avg > 0 else 0
        velocity_reports_data = asyncio.run(
            self.team_velocity_facade.get_velocity_reports_data(
                member_group_id, DISPLAY_PERIODS + extra_periods, use_custom_filter
            )
        )

        velocity_chart = self.team_velocity_facade.get_velocity_chart_data(
            velocity_reports_data, rolling_avg, DISPLAY_PERIODS if rolling_avg > 0 else 0
        )
        story_points_chart = self.team_velocity_facade.get_story_points_chart_data(velocity_reports_data)

        context["month_velocity"] = chronological_chart_json(velocity_chart)
        context["month_sp"] = chronological_chart_json(story_points_chart, DISPLAY_PERIODS)
        context["velocity_summary"] = VelocitySummaryUtils.summarize(velocity_reports_data, DISPLAY_PERIODS)
        context["success"] = True


class TeamVelocityTasksView(BaseVelocityTasksView):

    def populate_context(self, context, **kwargs):
        context["task_groups"] = []

        period, member_group_id, use_custom_filter = self._parse_request_params()

        start_date, end_date = self._parse_month_period(period)
        velocity_tasks = asyncio.run(
            self.tasks_velocity_facade.get_team_tasks(
                start_date, end_date, member_group_id, use_custom_filter
            )
        )
        context["task_groups"] = self._build_task_hierarchy(velocity_tasks, period)

    def _parse_request_params(self):
        period = self.request.GET.get('period', '')
        member_group_id = self.request.GET.get('member_group_id')
        use_custom_filter = self.request.GET.get('use_custom_filter') == 'true'
        return period, member_group_id, use_custom_filter
