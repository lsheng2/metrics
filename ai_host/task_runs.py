from ai_base_runtime import (
    RuntimeBusy, RuntimeCallTimeout, RuntimeFault, RuntimeNotRunning,
    RuntimeStartTimeout,
    retry_class,
)
from ai_base_runtime.apps import RunCancelResponse, RunResult, RunSnapshot, RunSubmit
from ai_base_runtime.contracts import canonical_digest, canonical_json
from ai_base_runtime.spi import Principal

from project_management.app.domain.capture_values import decode_json, sha256_bytes
from project_management.app.domain.task_runs import (
    TaskDispatch, TaskPrincipal, TaskResultSummary, TaskRunCancellation,
    TaskRunAdmissionMetadata, TaskRunError, TaskRunRequest, TaskRunResult, TaskRunSnapshot, TaskUsage,
)


CALL_TIMEOUT_SECONDS = 30
APP_ID = 'metrics'


def _invalid():
    return TaskRunError('RUN_INVALID', retry='no')


def _principal(value):
    if not isinstance(value, TaskPrincipal):
        raise TypeError('TaskPrincipal is required')
    return Principal(id=value.runtime_subject, display_name=value.display_name, anonymous=value.anonymous)


def _request(value):
    if not isinstance(value, TaskRunRequest):
        raise TypeError('TaskRunRequest is required')
    content = decode_json(value.input_json.encode('utf-8'))
    return RunSubmit(
        app_id=APP_ID, profile_id=value.profile_id, profile_version=value.profile_version,
        input=content, input_sha256=canonical_digest(content),
        client_run_key=value.client_run_key, deadline_at=value.deadline_at,
        limits=value.limits,
        minimum_result_retention_seconds=value.minimum_result_retention_seconds,
        correlation_id=value.correlation_id,
    )


def _usage(value):
    if value is None:
        return None
    return TaskUsage(
        input_tokens=value.input_tokens, output_tokens=value.output_tokens,
        total_tokens=value.total_tokens, source=value.source,
    )


def _dispatch(value):
    return TaskDispatch(
        provider=value.provider, model=value.model, runtime_version=value.runtime_version,
        profile_definition_sha256=value.profile_definition_digest,
        tool_definition_sha256=value.tool_definition_digest,
        dispatched=value.dispatched, uncertainty=value.uncertainty, usage=_usage(value.usage),
    )


def _error(value):
    return (None, None) if value is None else (value.code, retry_class(value.code))


def _check_binding(request, value, run_id=None):
    if not isinstance(request, TaskRunRequest):
        raise TypeError('TaskRunRequest is required')
    if (value.app_id != APP_ID or value.profile_id != request.profile_id
            or value.profile_version != request.profile_version
            or value.input_sha256 != canonical_digest(decode_json(request.input_json.encode('utf-8')))
            or value.dispatch.profile_definition_digest != request.profile_definition_sha256
            or run_id is not None and value.run_id != run_id):
        raise _invalid()


def _snapshot(request, value, run_id=None):
    if not isinstance(value, RunSnapshot):
        raise _invalid()
    _check_binding(request, value, run_id)
    if (value.result.output_schema_sha256 is not None
            and value.result.output_schema_sha256 != request.output_schema_sha256):
        raise _invalid()
    code, retry = _error(value.error)
    return TaskRunSnapshot(
        run_id=value.run_id, profile_id=value.profile_id, profile_version=value.profile_version,
        status=value.status, input_sha256=value.input_sha256,
        source_input_sha256=request.input_sha256,
        effective_input_sha256=value.effective_input_sha256, dispatch=_dispatch(value.dispatch),
        result=TaskResultSummary(
            output_sha256=value.result.output_sha256,
            output_schema_sha256=value.result.output_schema_sha256,
            usage=_usage(value.result.usage),
        ),
        error_code=code, retry=retry,
    )


def _result(request, value, run_id):
    if not isinstance(value, RunResult):
        raise _invalid()
    _check_binding(request, value, run_id)
    try:
        raw = canonical_json(value.content)
    except (TypeError, ValueError, RecursionError):
        raise _invalid() from None
    if (value.output_schema_sha256 != request.output_schema_sha256
            or sha256_bytes(raw) != value.output_sha256):
        raise _invalid()
    code, retry = _error(value.error)
    return TaskRunResult(
        run_id=value.run_id, profile_id=value.profile_id, profile_version=value.profile_version,
        status=value.status, input_sha256=value.input_sha256,
        source_input_sha256=request.input_sha256,
        effective_input_sha256=value.effective_input_sha256,
        output_schema_sha256=value.output_schema_sha256, output_sha256=value.output_sha256,
        content_json=raw.decode('utf-8'), dispatch=_dispatch(value.dispatch),
        usage=_usage(value.usage), error_code=code, retry=retry,
    )


class RuntimeTaskRunPort:
    def __init__(self, task_runs, *, admission_metadata):
        self._task_runs = task_runs
        if admission_metadata is not None and not isinstance(admission_metadata, TaskRunAdmissionMetadata):
            raise TypeError('TaskRunAdmissionMetadata is required')
        self._admission_metadata = admission_metadata

    def admission_metadata(self):
        if self._admission_metadata is None:
            raise TaskRunError('RUN_UNAVAILABLE', retry='repair', runtime_code='model_not_configured')
        return self._admission_metadata

    def _call(self, method, principal, argument, *, timeout=CALL_TIMEOUT_SECONDS):
        try:
            return method(_principal(principal), argument, timeout=timeout)
        except RuntimeFault as error:
            code = error.code
            if isinstance(error, RuntimeBusy):
                code = 'RUN_BUSY'
            elif isinstance(error, (RuntimeNotRunning, RuntimeCallTimeout, RuntimeStartTimeout)):
                code = 'RUN_UNAVAILABLE'
            raise TaskRunError(code, runtime_code=error.code, retry=error.retry) from None

    def start(self, principal, request):
        submitted = _request(request)
        return _snapshot(request, self._call(self._task_runs.start, principal, submitted))

    def lookup(self, principal, request, *, timeout=CALL_TIMEOUT_SECONDS):
        value = self._call(self._task_runs.lookup, principal, _request(request), timeout=timeout)
        return None if value is None else _snapshot(request, value)

    def get(self, principal, request, run_id, *, timeout=CALL_TIMEOUT_SECONDS):
        return _snapshot(request, self._call(self._task_runs.get, principal, run_id, timeout=timeout), run_id)

    def result(self, principal, request, run_id):
        return _result(request, self._call(self._task_runs.result, principal, run_id), run_id)

    def cancel(self, principal, run_id, *, timeout=CALL_TIMEOUT_SECONDS):
        value = self._call(self._task_runs.cancel, principal, run_id, timeout=timeout)
        if not isinstance(value, RunCancelResponse) or value.run_id != run_id:
            raise _invalid()
        return TaskRunCancellation(run_id=value.run_id, canceled=value.canceled)


def admission_metadata_from_host_config(config, runtime_version):
    model = getattr(config, 'model', None)
    if model is None:
        return None
    return TaskRunAdmissionMetadata(
        model_identity={'provider': model.provider, 'model': model.name},
        runtime_version=runtime_version,
    )
