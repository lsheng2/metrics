from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class ChartWorkflowRequest:
    profile_id: str
    chart_id: str
    requested_series: tuple[str, ...]
    range_mode: str
    range_start: str
    range_end: str
    visualization: str = 'timeseries'
    panel_title: str = ''
    render_config: dict | None = None


@dataclass(frozen=True, slots=True)
class ChartPublicationPreview:
    workflow: dict
    content: dict | None = None

    @property
    def ready(self):
        return self.content is not None


@dataclass(frozen=True, slots=True)
class ApprovedChartPublication:
    """Host transfer after runtime authorization, never a model or HTTP input."""

    preview_bytes: bytes
    preview_digest: str
    approval_id: str
    tool_call_id: str
    run_id: str
    decided_by: str
    decided_at: datetime


def normalized_grafana_base_url(value):
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        return None
    return value.rstrip('/')
