from ..container import ui_web_container
from .graceful_template_view import GracefulTemplateView


class DataHealthView(GracefulTemplateView):
    template_name = 'data_health.html'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_health_facade = ui_web_container.data_health_facade

    def populate_context(self, context, **kwargs):
        context['data_health'] = self.data_health_facade.get_data_health()
        context['build_page_title'] = 'Data Health'
