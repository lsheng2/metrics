from django.conf import settings

from project_management.app.domain.run_contracts import RunError
from project_management.app.domain.task_runs import TaskPrincipal


def task_principal(actor, project_id=None, stage_id=None):
    users = settings.METRICS_BASIC_AUTH_USERS
    subject = actor.subject
    if users is None:
        if subject != 'local_operator':
            raise RunError('RUN_UNAVAILABLE')
        username, anonymous = 'local_operator', True
    else:
        if subject == 'local_operator':
            username = getattr(settings, 'METRICS_PROJECT_LOCAL_OPERATOR_USERNAME', '')
        elif subject.startswith('basic:'):
            username = subject[len('basic:'):]
        else:
            raise RunError('RUN_UNAVAILABLE')
        if username not in users:
            raise RunError('RUN_UNAVAILABLE')
        anonymous = False
    return TaskPrincipal(
        subject=subject, runtime_subject=username, display_name=username, anonymous=anonymous,
    )
