from datetime import date, timedelta

from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


class BugTrendView(GracefulTemplateView):
    template_name = 'bug_trend.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['partials/bug_trend_content.html']
        return [self.template_name]

    def populate_context(self, context, **kwargs):
        self._populate_common_context(context)
        scope_options = context['scope_options']
        if not scope_options:
            context['chart_json'] = '{}'
            context['selected_scope_id'] = ''
            context['unavailable_reason'] = 'Create a saved Jira scope before opening the bug trend dashboard.'
            return

        selected_scope_id = int(self.request.GET.get('scope_id') or scope_options[0].id)
        begin, end = self._date_range()
        chart_data = self.bug_trend_facade.get_chart_data(selected_scope_id, begin, end)
        context['selected_scope_id'] = selected_scope_id
        context['begin'] = begin.isoformat()
        context['end'] = end.isoformat()
        context['chart_json'] = self.bug_trend_facade.get_chart_json(chart_data)
        context['unavailable_reason'] = chart_data.unavailable_reason

    def _populate_common_context(self, context):
        context['scope_options'] = self.bug_trend_facade.get_scope_options()
        context['build_page_title'] = 'Bug Trend Indicator'

    def _date_range(self):
        today = date.today()
        default_begin = today - timedelta(days=27)
        begin = date.fromisoformat(self.request.GET.get('begin') or default_begin.isoformat())
        end = date.fromisoformat(self.request.GET.get('end') or today.isoformat())
        return begin, end


class BugTrendChartView(BugTrendView):
    template_name = 'partials/bug_trend_chart.html'

    def get_template_names(self):
        return [self.template_name]


class BugTrendDrilldownView(GracefulTemplateView):
    template_name = 'partials/bug_trend_drilldown.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bug_trend_facade = ui_web_container.bug_trend_facade

    def populate_context(self, context, **kwargs):
        calculation_run_id = self.request.GET.get('run', '')
        bucket_id = self.request.GET.get('bucket', '')
        series_name = self.request.GET.get('series', '')
        drilldown = self.bug_trend_facade.get_drilldown_data(calculation_run_id, bucket_id, series_name)
        context['drilldown'] = drilldown
