from dataclasses import dataclass

from project_management.app.domain.run_contracts import RunError


@dataclass(frozen=True, slots=True)
class LocalTaskRunPort:
    task_runs: object
    principal_resolver: object


class LocalRuntimeCleanupError(RunError):
    def __init__(self):
        super().__init__('RUN_UNAVAILABLE')


_LOCAL_FACTORY = None


def register_local_task_run_port_factory(factory):
    global _LOCAL_FACTORY
    if not callable(factory) or _LOCAL_FACTORY is not None and _LOCAL_FACTORY is not factory:
        raise RunError('RUN_INVALID')
    _LOCAL_FACTORY = factory


def open_local_task_run_port():
    if _LOCAL_FACTORY is None:
        raise RunError('RUN_UNAVAILABLE')
    return _LOCAL_FACTORY()
