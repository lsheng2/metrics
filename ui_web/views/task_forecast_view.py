import asyncio

from forecast.app.domain.model.enums import TaskScope
from ..container import ui_web_container
from ..utils.chart_json_utils import ChartJsonUtils
from .graceful_template_view import GracefulTemplateView


class TaskForecastView(GracefulTemplateView):
    template_name = 'task_forecast.html'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ["partials/task_forecast_content.html"]
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        request_data = ui_web_container.task_forecast_convertor.extract_request_data_from_request(self.request)
        context["forecast_params"] = request_data
        context["task_forecast"] = None
        context["chart_data"] = ""
        if not request_data.task_id:
            return

        # Only a forecast needs the tracker-backed facade; the empty form renders without one.
        task_forecast_facade = ui_web_container.task_forecast_facade
        task_hierarchy = asyncio.run(task_forecast_facade.get_task_forecast_hierarchy_data(request_data))
        forecast_chart = task_forecast_facade.get_forecast_chart_from_data(task_hierarchy)

        context["task_forecast"] = task_forecast_facade.get_forecast_summary_from_data(task_hierarchy)
        context["chart_data"] = ChartJsonUtils.convert_chart_data_to_timeline_chartjs_json(
            forecast_chart) if forecast_chart else ""
        context["include_done_tasks"] = request_data.task_scope == TaskScope.ALL
