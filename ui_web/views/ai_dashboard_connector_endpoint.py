from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


CONNECTOR_CONTENT_TYPE = 'application/json'
BODYLESS_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})


def connector_endpoint(view_func):
    # CSRF exemption stays safe only while a cross-site browser request must pass a CORS preflight,
    # so every body-carrying connector request has to be JSON.
    @wraps(view_func)
    def guarded(request, *args, **kwargs):
        if request.method not in BODYLESS_METHODS and request.content_type != CONNECTOR_CONTENT_TYPE:
            return JsonResponse({'error': f'Content-Type must be {CONNECTOR_CONTENT_TYPE}.'}, status=415)
        return view_func(request, *args, **kwargs)

    return csrf_exempt(guarded)
