from contextlib import contextmanager

from ai_base_runtime import RuntimeBusy, RuntimeFault, start_blocking

from ai_host.admission import RuntimeCandidateError, admit_runtime_candidate
from ai_host.host import MetricsHost
from ai_host.package import METRICS_APP
from ai_host.principals import task_principal
from ai_host.settings import RUNTIME_START_SECONDS, build_runtime_settings
from ai_host.task_runs import RuntimeTaskRunPort, admission_metadata_from_host_config
from project_management.app.api.project_runs import RunError
from project_management.app.api.task_runtime import LocalRuntimeCleanupError, LocalTaskRunPort


@contextmanager
def local_task_run_port():
    context = handle = None
    try:
        runtime_record = admit_runtime_candidate()
        host = MetricsHost()
        host.config.state_dir.mkdir(parents=True, exist_ok=True)
        context = start_blocking(
            build_runtime_settings(), host, (METRICS_APP,), start_timeout=RUNTIME_START_SECONDS,
        )
        with context as handle:
            yield LocalTaskRunPort(
                RuntimeTaskRunPort(
                    handle.blocking.task_runs,
                    admission_metadata=admission_metadata_from_host_config(host.config, runtime_record['version']),
                ),
                task_principal,
            )
    except RuntimeBusy:
        raise RunError('RUN_BUSY') from None
    except (RuntimeFault, RuntimeCandidateError, OSError):
        raise RunError('RUN_UNAVAILABLE') from None
    finally:
        failure = None if context is None else context.startup_failure
        stopped = None if handle is None else handle.stop_result
        rollback = None if failure is None else failure.rollback_result
        if (handle is not None and (stopped is None or not stopped.completed)
                or rollback is not None and not rollback.completed):
            raise LocalRuntimeCleanupError() from None
