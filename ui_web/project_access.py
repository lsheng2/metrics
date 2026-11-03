from django.conf import settings
from django.http import HttpResponse

from project_management.app.api import ProjectActor


class ProjectAccessError(Exception):
    def __init__(self, status_code, message, challenge=False):
        self.status_code = status_code
        self.message = message
        self.challenge = challenge
        super().__init__(message)

    def to_response(self):
        response = HttpResponse(self.message, status=self.status_code)
        if self.challenge:
            response['WWW-Authenticate'] = 'Basic realm="Restricted"'
        return response


def project_actor(request) -> ProjectActor:
    username = getattr(request, 'metrics_basic_auth_username', None)
    if not username:
        raise ProjectAccessError(401, 'Unauthorized', True)
    local_username = getattr(settings, 'METRICS_PROJECT_LOCAL_OPERATOR_USERNAME', '')
    if not _valid_identity(username) or (local_username and not _valid_identity(local_username)):
        raise ProjectAccessError(403, 'Forbidden')
    if local_username and username == local_username:
        return ProjectActor('local_operator')
    subject = f'basic:{username}'
    if not _valid_identity(subject):
        raise ProjectAccessError(403, 'Forbidden')
    return ProjectActor(subject)


def project_access_response(error: ProjectAccessError):
    return error.to_response()


def private_no_store(response):
    response['Cache-Control'] = 'private, no-store'
    return response


def _valid_identity(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 160
        and not any(ord(char) < 32 for char in value)
    )
