from django.apps import AppConfig


class AiHostConfig(AppConfig):
    name = 'ai_host'
    verbose_name = 'AI Runtime Host'

    def ready(self):
        from project_management.app.api.task_runtime import register_local_task_run_port_factory
        register_local_task_run_port_factory(_open_local_port)


def _open_local_port():
    from ai_host.local_runtime import local_task_run_port
    return local_task_run_port()
