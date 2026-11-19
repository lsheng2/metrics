from typing import Optional, Dict

from django.conf import settings
from django.http import HttpResponse

from metrics.auth import BASIC_AUTH_CHALLENGE, check_basic_authorization


class BasicAuthMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def _load_users(self) -> Optional[Dict[str, str]]:
        return settings.METRICS_BASIC_AUTH_USERS

    def __call__(self, request):
        request.metrics_basic_auth_username = None
        users = self._load_users()
        auth = request.META.get('HTTP_AUTHORIZATION')
        identity = check_basic_authorization(users, auth)
        if identity is None:
            return self._unauthorized()
        if identity.anonymous:
            return self.get_response(request)
        request.metrics_basic_auth_username = identity.username
        return self.get_response(request)

    @staticmethod
    def _unauthorized() -> HttpResponse:
        response = HttpResponse('Unauthorized', status=401)
        response['WWW-Authenticate'] = BASIC_AUTH_CHALLENGE
        return response
