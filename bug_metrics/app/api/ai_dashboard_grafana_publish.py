from datetime import date, timedelta
from pathlib import Path
import base64
import json
import re
import urllib.parse
import urllib.request

from django.conf import settings

from .ai_dashboard_composition_contracts import DashboardAiPublishRequest


def import_grafana_dashboard_payload(grafana_base_url: str, dashboard: dict, username: str, password: str) -> dict:
    payload = json.dumps({
        'dashboard': dashboard,
        'overwrite': True,
        'message': 'Approved AI Dashboard local demo publish',
    }).encode('utf-8')
    request = urllib.request.Request(f'{grafana_base_url}/api/dashboards/db', data=payload, method='POST')
    request.add_header('Content-Type', 'application/json')
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    request.add_header('Authorization', f'Basic {token}')
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def configured_grafana_base_url() -> str:
    configured = str(settings.METRICS_AI_GRAFANA_BASE_URL).rstrip('/')
    if configured != 'http://127.0.0.1:3001':
        return configured
    summary_path = Path(settings.METRICS_STATE_DIR) / 'e2e' / 'bug_trend_ports.json'
    if not summary_path.exists():
        return configured
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    grafana_port = summary.get('grafana_port')
    if not isinstance(grafana_port, int):
        return configured
    return f'http://127.0.0.1:{grafana_port}'


def grafana_dashboard_url(grafana_base_url: str, request: DashboardAiPublishRequest) -> str:
    query_values = {
        'orgId': '1',
        'var-profile_id': request.profile_id,
        'var-range_mode': request.range_mode,
        'var-begin_ww': request.range_start if request.range_mode == 'ww' else '',
        'var-end_ww': request.range_end if request.range_mode == 'ww' else '',
        **grafana_time_range(request),
        'timezone': 'browser',
    }
    query = urllib.parse.urlencode({key: value for key, value in query_values.items() if value})
    return f'{grafana_base_url}/d/{request.dashboard_uid}/ai-draft-dashboard?{query}'


def grafana_time_range(request: DashboardAiPublishRequest) -> dict:
    if request.range_mode == 'ww':
        begin, end = ww_range_to_dates(request.range_start, request.range_end)
        return {'from': f'{begin.isoformat()}T00:00:00', 'to': f'{end.isoformat()}T23:59:59'}
    return {'from': request.range_start, 'to': request.range_end}


def ww_range_to_dates(begin_ww: str, end_ww: str) -> tuple[date, date]:
    begin = ww_to_monday(begin_ww)
    end = ww_to_monday(end_ww) + timedelta(days=6)
    if begin > end:
        raise ValueError('range_start must be earlier than or equal to range_end.')
    return begin, end


def ww_to_monday(value: str) -> date:
    normalized = value.strip()
    if not re.fullmatch(r'\d{2}WW\d{2}', normalized, flags=re.IGNORECASE):
        raise ValueError('WW values must use YYWWNN format.')
    return date.fromisocalendar(2000 + int(normalized[:2]), int(normalized[4:]), 1)
