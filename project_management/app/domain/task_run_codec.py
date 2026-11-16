from collections.abc import Mapping
from dataclasses import fields
from datetime import datetime

from .captures import ArchiveError
from .task_runs import (
    TaskDispatch, TaskPrincipal, TaskResultSummary, TaskRunCancellation,
    TaskRunBinding, TaskRunRequest, TaskRunResult, TaskRunSnapshot, TaskUsage,
)


def _record(record_type, value):
    if not isinstance(value, Mapping) or set(value) != {field.name for field in fields(record_type)}:
        raise ValueError('Invalid task-run record shape')
    return dict(value)


def _construct(record_type, value):
    try:
        return record_type(**value)
    except (TypeError, ValueError, AttributeError, ArchiveError):
        raise ValueError('Invalid task-run record') from None


def principal_from_record(value):
    return _construct(TaskPrincipal, _record(TaskPrincipal, value))


def binding_from_record(value):
    data = _record(TaskRunBinding, value)
    data['principal'] = principal_from_record(data['principal'])
    return _construct(TaskRunBinding, data)


def request_from_record(value):
    data = _record(TaskRunRequest, value)
    try:
        if type(data['deadline_at']) is not str:
            raise ValueError
        data['deadline_at'] = datetime.fromisoformat(data['deadline_at'])
    except (TypeError, ValueError):
        raise ValueError('Invalid stored task deadline') from None
    return _construct(TaskRunRequest, data)


def usage_from_record(value):
    return None if value is None else _construct(TaskUsage, _record(TaskUsage, value))


def dispatch_from_record(value):
    data = _record(TaskDispatch, value)
    data['usage'] = usage_from_record(data['usage'])
    return _construct(TaskDispatch, data)


def result_summary_from_record(value):
    data = _record(TaskResultSummary, value)
    data['usage'] = usage_from_record(data['usage'])
    return _construct(TaskResultSummary, data)


def snapshot_from_record(value):
    data = _record(TaskRunSnapshot, value)
    data['dispatch'] = dispatch_from_record(data['dispatch'])
    data['result'] = result_summary_from_record(data['result'])
    return _construct(TaskRunSnapshot, data)


def result_from_record(value):
    data = _record(TaskRunResult, value)
    data['dispatch'] = dispatch_from_record(data['dispatch'])
    data['usage'] = usage_from_record(data['usage'])
    return _construct(TaskRunResult, data)


def cancellation_from_record(value):
    return _construct(TaskRunCancellation, _record(TaskRunCancellation, value))
