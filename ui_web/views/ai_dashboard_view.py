from datetime import date, timedelta
import json

from django.http import JsonResponse
from django.utils.translation import gettext
from django.views import View
from django.views.generic import TemplateView

from ai_host.pane import runtime_status
from bug_metrics.app.api.ai_publication_contracts import ChartWorkflowRequest
from ui_web.container import ui_web_container


_FORM_FIELDS = frozenset({
    'profile_id', 'chart_id', 'requested_series', 'range_mode', 'range_start',
    'range_end', 'panel_title', 'visualization',
})


class AiDashboardWorkflowView(TemplateView):
    template_name = 'ai_dashboard_workflow.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        facade = ui_web_container.bug_trend_facade
        catalog = facade.get_ai_dashboard_catalog_payload('')
        today = date.today()
        defaults = {
            'profile_id': '', 'chart_id': 'open_bug_trend', 'requested_series': 'new_critical_high',
            'range_mode': 'date', 'range_start': (today - timedelta(days=27)).isoformat(),
            'range_end': today.isoformat(), 'panel_title': '', 'visualization': 'timeseries',
        }
        values = {
            key: str(self.request.GET.get(key, defaults[key]) or '')
            for key in _FORM_FIELDS
        }
        context.update(
            form_values=values, ai_runtime=runtime_status(),
            profile_options=catalog.get('profiles', []),
            chart_options=[
                {'chart_id': chart_id, 'title': recipe.get('title', chart_id)}
                for chart_id, recipe in sorted(catalog.get('chart_recipes', {}).items())
            ],
            publish_history=facade.get_ai_chart_publications(10),
        )
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if set(request.POST) - _FORM_FIELDS - {'csrfmiddlewaretoken'}:
            context['workflow_error'] = gettext('The workflow request was rejected.')
            return self.render_to_response(context, status=400)
        values = {key: str(request.POST.get(key, context['form_values'][key]) or '') for key in _FORM_FIELDS}
        context['form_values'] = values
        chart = ChartWorkflowRequest(
            **{key: value for key, value in values.items() if key != 'requested_series'},
            requested_series=tuple(part.strip() for part in values['requested_series'].split(',') if part.strip()),
        )
        result = ui_web_container.bug_trend_facade.evaluate_ai_chart_workflow(chart)
        context['workflow_result'] = result
        context['normalized_render_config'] = json.dumps(
            result.get('normalized_render_config'), ensure_ascii=False, indent=2,
        ) if result.get('normalized_render_config') is not None else ''
        return self.render_to_response(context)


class AiPublishHistoryApiView(View):
    def get(self, request):
        try:
            if set(request.GET) - {'limit'}:
                raise ValueError()
            limit = int(request.GET.get('limit', '25'))
            result = ui_web_container.bug_trend_facade.get_ai_chart_publications(limit)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'invalid_history_query'}, status=400)
        return JsonResponse(result)
