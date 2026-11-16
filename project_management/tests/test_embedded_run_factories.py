import pytest
from django.test import override_settings

from project_management.app.api.project_runs import build_project_runtime
from project_management.app.api.project_runs import clear_project_runtime, install_project_runtime
from project_management.app.api.report_factories import build_report_assist_service
from project_management.app.domain.run_contracts import RunError
from project_management.app.domain.task_runs import TaskPrincipal


@pytest.mark.django_db
@override_settings(
    METRICS_PROJECT_RUN_ENABLED=True,
    METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Synthetic Test',
    METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='synthetic@example.test',
)
def test_runtime_factory_composes_real_services_with_the_supplied_task_port():
    port = object()

    def principal(actor, project_id=None, stage_id=None):
        return TaskPrincipal(
            subject=actor.subject, runtime_subject=actor.subject, display_name=actor.subject, anonymous=False,
        )

    runtime = build_project_runtime(task_runs=port, principal_resolver=principal)
    assert runtime.run_service.analysis_service.task_run_port is port
    assert runtime.run_service.principal_resolver is principal
    assert runtime.run_service.task_profile.id == 'metrics.project_summary'
    assert runtime.worker.run_service is runtime.run_service
    assert runtime.worker.daily_preparation_service.run_service is runtime.run_service
    assert runtime._thread is None


@pytest.mark.django_db
@override_settings(METRICS_PROJECT_RUN_ENABLED=True)
def test_runtime_factory_refuses_missing_port_without_a_legacy_factory_fallback():
    with pytest.raises(RunError):
        build_project_runtime(task_runs=None, principal_resolver=lambda *args: None)


@pytest.mark.django_db
@override_settings(
    METRICS_PROJECT_RUN_ENABLED=True,
    METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Synthetic Test',
    METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='synthetic@example.test',
)
def test_report_assist_factory_consumes_the_installed_project_runtime_port():
    port = object()
    resolver = lambda actor, project_id, stage_id: actor
    runtime = build_project_runtime(task_runs=port, principal_resolver=resolver)
    install_project_runtime(runtime)
    try:
        service = build_report_assist_service(draft_service=runtime.run_service.draft_service)
        assert service.task_run_port is port
        actor = object()
        assert service.principal_resolver(actor) is actor
    finally:
        clear_project_runtime(runtime)
