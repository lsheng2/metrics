from time import monotonic

from project_management.app.domain.run_contracts import RunError
from project_management.storage.read_workers import ordered_read_map


def list_operations(repository, *, limit, read_map=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise RunError('RUN_INVALID')
    deadline = monotonic() + 10

    def active():
        if monotonic() >= deadline:
            raise RunError('RUN_STORAGE_UNAVAILABLE')

    def read(path):
        try:
            return repository.current(path.name)
        except RunError as error:
            if error.code == 'RUN_STORAGE_INVALID':
                raise
            return None

    if read_map is None:
        with ordered_read_map(read, repository._operation_dirs(), active) as results:
            operations = [row for row in results if row is not None]
    else:
        operations = [row for row in read_map(read, repository._operation_dirs()) if row is not None]
    operations.sort(key=lambda row: (row.created_at, row.operation_id), reverse=True)
    return tuple(operations[:limit])
