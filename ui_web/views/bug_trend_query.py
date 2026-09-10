from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse


CHART_DATA_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'chart_id'})
CHART_DATA_OPTIONAL_PARAMS = frozenset()
EVIDENCE_REQUIRED_PARAMS = frozenset({'scope_id', 'begin', 'end', 'run', 'chart_id'})
EVIDENCE_OPTIONAL_PARAMS = frozenset({'bucket', 'series', 'owner', 'status', 'severity', 'component', 'text'})


def validate_query_contract(request, required_params, optional_params):
    provided_params = set(request.GET.keys())
    missing_params = sorted(param for param in required_params if not request.GET.get(param))
    unknown_params = sorted(provided_params - required_params - optional_params)
    if missing_params or unknown_params:
        return JsonResponse({
            'error': 'Invalid Bug Trend API query parameters.',
            'missing_params': missing_params,
            'unknown_params': unknown_params,
        }, status=400)
    return None


def chart_id_error_response(error):
    if isinstance(error, ObjectDoesNotExist):
        return JsonResponse({'error': 'Unknown or unpublished Bug Trend chart.', 'chart_id': ''}, status=400)
    if isinstance(error, ValueError):
        return JsonResponse({'error': str(error)}, status=400)
    return None


def parse_date_query(value: str, field_name: str):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{field_name} must be an ISO date.')
