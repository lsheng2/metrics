from ai_base_runtime.apps import HostAction


async def _open_view(principal, payload):
    return dict(payload)


_VIEW_SCHEMA = {
    'type': 'object',
    'properties': {
        'chart_id': {'type': 'string', 'pattern': '^[A-Za-z0-9._:-]{1,160}$'},
        'bucket': {'type': 'string', 'maxLength': 160},
        'series': {'type': 'string', 'maxLength': 160},
    },
    'required': ['chart_id'],
    'additionalProperties': False,
}

WORKBENCH_HOST_ACTIONS = tuple(
    HostAction(name=name, handler=_open_view, input_schema=_VIEW_SCHEMA)
    for name in ('metrics.openChart', 'metrics.openEvidence')
)
