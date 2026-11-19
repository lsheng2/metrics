from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import math
import re
from types import MappingProxyType
from typing import Protocol

from .capture_values import canonical_bytes, decode_json, sha256_bytes


RUN_STATES = frozenset({'queued', 'running', 'succeeded', 'failed', 'timed_out', 'canceled', 'indeterminate'})
RETRY_CLASSES = frozenset({'correct', 'observe', 'repair', 'fresh', 'no'})


def _text(value):
    if type(value) is not str or not value or value != value.strip():
        raise ValueError('Invalid task-run text')
    return value


def _digest(value, *, optional=False):
    if optional and value is None:
        return None
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Invalid task-run digest')
    return value


def _error(code, retry):
    if code is None and retry is None:
        return
    if type(code) is not str or not code or retry not in RETRY_CLASSES:
        raise ValueError('Invalid task-run error')


class TaskRunError(Exception):
    def __init__(self, code, *, retry, runtime_code=None):
        _text(code)
        if retry not in RETRY_CLASSES:
            raise ValueError('Invalid task-run retry class')
        if runtime_code is not None:
            _text(runtime_code)
        self.code = code
        self.runtime_code = runtime_code
        self.retry = retry
        super().__init__(code)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskPrincipal:
    subject: str
    runtime_subject: str
    display_name: str
    anonymous: bool

    def __post_init__(self):
        _text(self.subject)
        _text(self.runtime_subject)
        _text(self.display_name)
        if type(self.anonymous) is not bool:
            raise ValueError('Invalid task principal')


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunBinding:
    principal: TaskPrincipal
    profile_id: str
    profile_version: str
    profile_definition_sha256: str
    output_schema_sha256: str
    model_identity: Mapping[str, str]
    runtime_version: str

    def __post_init__(self):
        if not isinstance(self.principal, TaskPrincipal):
            raise ValueError('Invalid task principal')
        _text(self.profile_id)
        _text(self.profile_version)
        _text(self.runtime_version)
        if not self.profile_id.startswith('metrics.') or self.profile_version == 'latest':
            raise ValueError('An exact Metrics task profile is required')
        _digest(self.profile_definition_sha256)
        _digest(self.output_schema_sha256)
        if not isinstance(self.model_identity, Mapping) or set(self.model_identity) != {'provider', 'model'}:
            raise ValueError('Invalid model identity')
        model_identity = dict(self.model_identity)
        _text(model_identity['provider'])
        _text(model_identity['model'])
        object.__setattr__(self, 'model_identity', MappingProxyType(model_identity))


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunAdmissionMetadata:
    model_identity: Mapping[str, str]
    runtime_version: str

    def __post_init__(self):
        _text(self.runtime_version)
        if not isinstance(self.model_identity, Mapping) or set(self.model_identity) != {'provider', 'model'}:
            raise ValueError('Invalid model identity')
        model_identity = dict(self.model_identity)
        _text(model_identity['provider'])
        _text(model_identity['model'])
        object.__setattr__(self, 'model_identity', MappingProxyType(model_identity))


class TaskRunPort(Protocol):
    def admission_metadata(self) -> TaskRunAdmissionMetadata:
        ...

    def start(self, principal: TaskPrincipal, request: 'TaskRunRequest'):
        ...

    def lookup(self, principal: TaskPrincipal, request: 'TaskRunRequest', *, timeout=None):
        ...

    def get(self, principal: TaskPrincipal, request: 'TaskRunRequest', run_id: str, *, timeout=None):
        ...

    def result(self, principal: TaskPrincipal, request: 'TaskRunRequest', run_id: str):
        ...

    def cancel(self, principal: TaskPrincipal, run_id: str, *, timeout=None):
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunRequest:
    profile_id: str
    profile_version: str
    profile_definition_sha256: str
    output_schema_sha256: str
    input_json: str
    input_sha256: str
    client_run_key: str
    deadline_at: datetime
    limits: Mapping[str, int | float]
    minimum_result_retention_seconds: int
    correlation_id: str | None = None

    def __post_init__(self):
        _text(self.profile_id)
        _text(self.profile_version)
        _text(self.client_run_key)
        if not self.profile_id.startswith('metrics.') or self.profile_version == 'latest':
            raise ValueError('An exact Metrics task profile is required')
        for value in (self.profile_definition_sha256, self.output_schema_sha256, self.input_sha256):
            _digest(value)
        raw = self.input_json.encode('utf-8')
        if canonical_bytes(decode_json(raw)) != raw or sha256_bytes(raw) != self.input_sha256:
            raise ValueError('Task input does not match its canonical digest')
        if not isinstance(self.deadline_at, datetime) or self.deadline_at.utcoffset() is None:
            raise ValueError('An aware task deadline is required')
        object.__setattr__(self, 'deadline_at', self.deadline_at.astimezone(UTC))
        if not isinstance(self.limits, Mapping):
            raise ValueError('Invalid task limits')
        limits = dict(self.limits)
        for key, value in limits.items():
            if (type(key) is not str or re.fullmatch('[a-z][a-z0-9_]*', key) is None
                    or type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValueError('Invalid task limit')
        object.__setattr__(self, 'limits', MappingProxyType(limits))
        if type(self.minimum_result_retention_seconds) is not int or self.minimum_result_retention_seconds <= 0:
            raise ValueError('Invalid task retention')
        if self.correlation_id is not None:
            _text(self.correlation_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskUsage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    source: str

    def __post_init__(self):
        if self.source not in {'provider_reported', 'deterministic_estimate', 'unavailable'}:
            raise ValueError('Invalid usage source')
        for value in (self.input_tokens, self.output_tokens, self.total_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Invalid token count')


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskDispatch:
    provider: str
    model: str
    runtime_version: str
    profile_definition_sha256: str
    tool_definition_sha256: str | None
    dispatched: bool
    uncertainty: str
    usage: TaskUsage | None

    def __post_init__(self):
        for value in (self.provider, self.model, self.runtime_version):
            _text(value)
        _digest(self.profile_definition_sha256)
        _digest(self.tool_definition_sha256, optional=True)
        if type(self.dispatched) is not bool or self.uncertainty not in {'not_dispatched', 'unknown', 'dispatched'}:
            raise ValueError('Invalid dispatch observation')


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskResultSummary:
    output_sha256: str | None
    output_schema_sha256: str | None
    usage: TaskUsage | None

    def __post_init__(self):
        _digest(self.output_sha256, optional=True)
        _digest(self.output_schema_sha256, optional=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunSnapshot:
    run_id: str
    profile_id: str
    profile_version: str
    status: str
    source_input_sha256: str
    input_sha256: str
    effective_input_sha256: str | None
    dispatch: TaskDispatch
    result: TaskResultSummary
    error_code: str | None
    retry: str | None

    def __post_init__(self):
        for value in (self.run_id, self.profile_id, self.profile_version):
            _text(value)
        if self.status not in RUN_STATES:
            raise ValueError('Invalid task status')
        _digest(self.source_input_sha256)
        _digest(self.input_sha256)
        _digest(self.effective_input_sha256, optional=True)
        if not isinstance(self.dispatch, TaskDispatch) or not isinstance(self.result, TaskResultSummary):
            raise ValueError('Invalid task observation')
        _error(self.error_code, self.retry)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunResult:
    run_id: str
    profile_id: str
    profile_version: str
    status: str
    source_input_sha256: str
    input_sha256: str
    effective_input_sha256: str
    output_schema_sha256: str
    output_sha256: str
    content_json: str
    dispatch: TaskDispatch
    usage: TaskUsage | None
    error_code: str | None
    retry: str | None

    def __post_init__(self):
        for value in (self.run_id, self.profile_id, self.profile_version):
            _text(value)
        if self.status not in RUN_STATES:
            raise ValueError('Invalid task result status')
        for value in (self.source_input_sha256, self.input_sha256, self.effective_input_sha256,
                      self.output_schema_sha256, self.output_sha256):
            _digest(value)
        raw = self.content_json.encode('utf-8')
        decode_json(raw)
        # Runtime output bytes retain the runtime digest, not the archive's JSON encoding.
        if sha256_bytes(raw) != self.output_sha256:
            raise ValueError('Task output does not match its digest')
        if not isinstance(self.dispatch, TaskDispatch):
            raise ValueError('Invalid task dispatch')
        _error(self.error_code, self.retry)


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunCancellation:
    run_id: str
    canceled: bool

    def __post_init__(self):
        _text(self.run_id)
        if type(self.canceled) is not bool:
            raise ValueError('Invalid cancellation acknowledgement')
