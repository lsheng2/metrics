from project_management.app.domain.run_contracts import (
    DailyRunRequest,
    DailyRunTarget,
    ItemRunResult,
    RunError,
    RunOperation,
    RunPolicy,
    RunRequest,
    RuntimeStopResult,
)
from project_management.services.project_run_worker import ProjectRunWorker
from project_management.services.project_runs import ProjectRunService
from project_management.runtime import (
    ProjectRunRuntime,
    build_project_runtime,
    build_run_read_service,
    clear_project_runtime,
    get_project_runtime,
    install_project_runtime,
)


def get_report_preparation_service():
    runtime = get_project_runtime()
    return None if runtime is None else getattr(runtime.worker, 'daily_preparation_service', None)


__all__ = [
    'ItemRunResult',
    'DailyRunRequest',
    'DailyRunTarget',
    'ProjectRunService',
    'ProjectRunRuntime',
    'ProjectRunWorker',
    'RunError',
    'RunOperation',
    'RunPolicy',
    'RunRequest',
    'RuntimeStopResult',
    'build_project_runtime',
    'build_run_read_service',
    'clear_project_runtime',
    'get_project_runtime',
    'get_report_preparation_service',
    'install_project_runtime',
]
