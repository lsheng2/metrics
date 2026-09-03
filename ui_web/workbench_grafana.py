from dataclasses import dataclass
from urllib.parse import urlencode

from bug_metrics.app.api.ai_dashboard_grafana_publish import configured_grafana_base_url

from .workbench_state import WorkbenchPageQueryState


@dataclass(frozen=True, slots=True)
class WorkbenchGrafanaPanel:
    dashboard_uid: str
    dashboard_slug: str
    panel_id: int
    title: str


DEFAULT_BUG_TREND_PANEL = WorkbenchGrafanaPanel(
    dashboard_uid='metrics-bug-trend-c-stock',
    dashboard_slug='metrics-bug-trend-c-stock-spike',
    panel_id=1,
    title='Bug Trend',
)


def grafana_panel_embed_url(state: WorkbenchPageQueryState, panel: WorkbenchGrafanaPanel = DEFAULT_BUG_TREND_PANEL) -> str:
    query = urlencode({
        key: value
        for key, value in {
            'orgId': '1',
            'panelId': str(panel.panel_id),
            'var-scope_id': state.scope_id,
            'var-begin': state.begin,
            'var-end': state.end,
            'timezone': 'browser',
            'theme': 'dark',
        }.items()
        if value
    })
    return f'{configured_grafana_base_url()}/d-solo/{panel.dashboard_uid}/{panel.dashboard_slug}?{query}'


def grafana_full_dashboard_url(state: WorkbenchPageQueryState, panel: WorkbenchGrafanaPanel = DEFAULT_BUG_TREND_PANEL) -> str:
    query = urlencode({
        key: value
        for key, value in {
            'orgId': '1',
            'var-scope_id': state.scope_id,
            'var-begin': state.begin,
            'var-end': state.end,
            'timezone': 'browser',
        }.items()
        if value
    })
    return f'{configured_grafana_base_url()}/d/{panel.dashboard_uid}/{panel.dashboard_slug}?{query}'
