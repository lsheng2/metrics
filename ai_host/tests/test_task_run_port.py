from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from ai_base_runtime import RuntimeCallTimeout, RuntimeNotRunning, RuntimeOperationError
from ai_base_runtime.apps import (
    DispatchObservation, ErrorInfo, ResultSummary, RunCancelResponse, RunResult,
    RunSnapshot, RunUsage,
)
from ai_base_runtime.contracts import canonical_digest, canonical_json

from ai_host.task_runs import RuntimeTaskRunPort
from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.task_runs import (
    TaskPrincipal, TaskRunAdmissionMetadata, TaskRunError, TaskRunRequest, TaskRunResult, TaskRunSnapshot,
)


DEFINITION = 'a' * 64
OUTPUT_SCHEMA = 'b' * 64
PRINCIPAL = TaskPrincipal(subject='basic:alice', runtime_subject='alice', display_name='Alice', anonymous=False)
ADMISSION = TaskRunAdmissionMetadata(
    model_identity={'provider': 'openai-compatible', 'model': 'scripted'},
    runtime_version='0.1.0',
)


def port(facade):
    return RuntimeTaskRunPort(facade, admission_metadata=ADMISSION)


def request():
    value = {'source': 'synthetic input'}
    return TaskRunRequest(
        profile_id='metrics.project_summary', profile_version='1',
        profile_definition_sha256=DEFINITION, output_schema_sha256=OUTPUT_SCHEMA,
        input_json=canonical_bytes(value).decode('utf-8'), input_sha256=content_hash(value),
        client_run_key='attempt-fixed', deadline_at=datetime.now(UTC) + timedelta(minutes=1),
        limits={'max_output_bytes': 65536}, minimum_result_retention_seconds=120,
        correlation_id='correlation-fixed',
    )


def snapshot(task, **changes):
    values = dict(
        run_id='run-fixed', app_id='metrics', profile_id=task.profile_id,
        profile_version=task.profile_version, status='queued',
        input_sha256=task.input_sha256, effective_input_sha256=None,
        dispatch=DispatchObservation(
            provider='openai-compatible', model='scripted', runtime_version='0.1.0',
            profile_definition_digest=DEFINITION, dispatched=False, uncertainty='unknown',
        ),
        result=ResultSummary(),
    )
    values.update(changes)
    return RunSnapshot(**values)


class RecordingFacade:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def _call(self, method, principal, argument, timeout):
        self.calls.append((method, principal, argument, timeout))
        if isinstance(self.value, Exception):
            raise self.value
        return self.value

    def start(self, principal, task, *, timeout):
        return self._call('start', principal, task, timeout)

    def lookup(self, principal, task, *, timeout):
        return self._call('lookup', principal, task, timeout)

    def get(self, principal, run_id, *, timeout):
        return self._call('get', principal, run_id, timeout)

    def result(self, principal, run_id, *, timeout):
        return self._call('result', principal, run_id, timeout)

    def cancel(self, principal, run_id, *, timeout):
        return self._call('cancel', principal, run_id, timeout)


def test_start_preserves_request_identity_without_legacy_wire():
    task = request()
    facade = RecordingFacade(snapshot(task))
    runtime_port = port(facade)
    first = runtime_port.start(PRINCIPAL, task)
    second = runtime_port.start(PRINCIPAL, task)
    assert isinstance(first, TaskRunSnapshot)
    assert first == second
    assert first.dispatch.uncertainty == 'unknown'
    assert first.dispatch.dispatched is False
    assert first.result.output_sha256 is None
    assert {field.name for field in fields(first)} == {
        'run_id', 'profile_id', 'profile_version', 'status', 'source_input_sha256', 'input_sha256',
        'effective_input_sha256', 'dispatch', 'result', 'error_code', 'retry',
    }
    assert not hasattr(runtime_port, 'get_by_client_key')
    for method, principal, sent, timeout in facade.calls:
        assert method == 'start' and timeout == 30
        assert (principal.id, principal.display_name, principal.anonymous) == (
            PRINCIPAL.runtime_subject, PRINCIPAL.display_name, PRINCIPAL.anonymous,
        )
        assert sent.app_id == 'metrics'
        assert sent.client_run_key == task.client_run_key
        assert sent.deadline_at == task.deadline_at
        assert sent.input == {'source': 'synthetic input'}
        assert sent.input_sha256 == task.input_sha256
        assert sent.correlation_id == task.correlation_id


def test_admission_metadata_must_be_explicit():
    with pytest.raises(TypeError):
        RuntimeTaskRunPort(RecordingFacade(None))


def test_admission_metadata_preserves_configured_model_identity():
    assert port(RecordingFacade(None)).admission_metadata() == ADMISSION


def test_not_configured_runtime_observes_without_inventing_admission_identity():
    task = request()
    runtime_port = RuntimeTaskRunPort(RecordingFacade(None), admission_metadata=None)

    with pytest.raises(TaskRunError) as error:
        runtime_port.admission_metadata()

    assert (error.value.code, error.value.runtime_code, error.value.retry) == (
        'RUN_UNAVAILABLE', 'model_not_configured', 'repair',
    )
    assert runtime_port.lookup(PRINCIPAL, task) is None


@pytest.mark.parametrize('changes', [
    {'app_id': 'other'},
    {'profile_id': 'metrics.other'},
    {'profile_version': 'different'},
    {'input_sha256': 'c' * 64},
    {'dispatch': DispatchObservation(
        provider='openai-compatible', model='scripted', runtime_version='0.1.0',
        profile_definition_digest='c' * 64,
    )},
])
def test_snapshot_mismatched_binding_is_rejected(changes):
    task = request()
    port = RuntimeTaskRunPort(RecordingFacade(snapshot(task, **changes)), admission_metadata=ADMISSION)
    with pytest.raises(TaskRunError, match='RUN_INVALID'):
        port.start(PRINCIPAL, task)


def test_get_does_not_turn_observation_into_admission():
    task = request()
    facade = RecordingFacade(snapshot(task))
    value = port(facade).get(PRINCIPAL, task, 'run-fixed')
    assert value.run_id == 'run-fixed'
    assert [(call[0], call[2], call[3]) for call in facade.calls] == [('get', 'run-fixed', 30)]


@pytest.mark.parametrize('found', [False, True])
def test_lookup_observes_original_request_without_admitting(found):
    task = request()
    facade = RecordingFacade(snapshot(task) if found else None)
    value = port(facade).lookup(PRINCIPAL, task)
    assert (value is not None) is found
    if found:
        assert value.run_id == 'run-fixed'
    assert len(facade.calls) == 1
    method, principal, sent, timeout = facade.calls[0]
    assert (method, principal.id, timeout) == ('lookup', PRINCIPAL.runtime_subject, 30)
    assert sent.client_run_key == task.client_run_key
    assert sent.deadline_at == task.deadline_at
    assert sent.input_sha256 == task.input_sha256


@pytest.mark.parametrize('error, code, runtime_code, retry', [
    (RuntimeCallTimeout(), 'RUN_UNAVAILABLE', 'runtime_call_timeout', 'observe'),
    (RuntimeNotRunning(), 'RUN_UNAVAILABLE', 'runtime_not_running', 'fresh'),
    (RuntimeOperationError('profile_disabled'), 'profile_disabled', 'profile_disabled', 'repair'),
])
def test_failure_preserves_registered_retry_class(error, code, runtime_code, retry):
    task = request()
    port = RuntimeTaskRunPort(RecordingFacade(error), admission_metadata=ADMISSION)
    with pytest.raises(TaskRunError) as caught:
        port.start(PRINCIPAL, task)
    assert (caught.value.code, caught.value.runtime_code, caught.value.retry) == (
        code, runtime_code, retry,
    )
    assert not hasattr(caught.value, 'recovery')
    assert not hasattr(caught.value, 'status')


def result(task, **changes):
    content = {'summary': 'Observed output'}
    values = dict(
        run_id='run-fixed', app_id='metrics', profile_id=task.profile_id,
        profile_version=task.profile_version, status='succeeded',
        input_sha256=task.input_sha256, effective_input_sha256='d' * 64,
        output_schema_sha256=OUTPUT_SCHEMA, output_sha256=content_hash(content),
        content=content,
        dispatch=DispatchObservation(
            provider='openai-compatible', model='scripted', runtime_version='0.1.0',
            profile_definition_digest=DEFINITION, dispatched=True, uncertainty='dispatched',
        ),
        usage=RunUsage(input_tokens=10, output_tokens=5, total_tokens=15, source='provider_reported'),
    )
    values.update(changes)
    return RunResult(**values)


def test_result_contains_only_observed_content_and_usage():
    task = request()
    actual = result(task)
    value = port(RecordingFacade(actual)).result(PRINCIPAL, task, 'run-fixed')
    assert isinstance(value, TaskRunResult)
    assert value.content_json == canonical_bytes(actual.content).decode('utf-8')
    assert value.output_sha256 == actual.output_sha256
    assert value.usage.input_tokens == 10
    assert value.usage.source == 'provider_reported'
    actual.content['summary'] = 'later mutation'
    assert 'later mutation' not in value.content_json
    assert not hasattr(value, 'accepted_at')
    assert not hasattr(value, 'provider_requests')


@pytest.mark.parametrize('changes', [
    {'output_sha256': 'e' * 64},
    {'output_schema_sha256': 'e' * 64},
    {'run_id': 'different-run'},
    {'app_id': 'other'},
])
def test_result_binding_and_content_digest_are_not_reconstructed(changes):
    task = request()
    port = RuntimeTaskRunPort(RecordingFacade(result(task, **changes)), admission_metadata=ADMISSION)
    with pytest.raises(TaskRunError, match='RUN_INVALID'):
        port.result(PRINCIPAL, task, 'run-fixed')


def test_cancel_preserves_ack_without_inventing_remote_stop_or_terminal_state():
    facade = RecordingFacade(RunCancelResponse(run_id='run-fixed', canceled=False))
    value = port(facade).cancel(PRINCIPAL, 'run-fixed')
    assert value.run_id == 'run-fixed' and value.canceled is False
    assert [(call[0], call[2], call[3]) for call in facade.calls] == [('cancel', 'run-fixed', 30)]
    assert {field.name for field in fields(value)} == {'run_id', 'canceled'}


def test_principal_is_not_coerced_from_arbitrary_objects():
    task = request()
    runtime_port = port(RecordingFacade(snapshot(task)))
    with pytest.raises(TypeError):
        runtime_port.start(SimpleNamespace(subject='basic:alice'), task)


def test_failed_run_uses_code_registry_not_nonexistent_error_retry_attribute():
    task = request()
    value = port(RecordingFacade(snapshot(
        task, status='failed', error=ErrorInfo(code='backend_failed'),
    ))).start(PRINCIPAL, task)
    assert value.error_code == 'backend_failed'
    assert value.retry == 'observe'


def test_request_detaches_limits_and_rejects_mismatched_input():
    task = request()
    limits = {'max_output_bytes': 1024}
    captured = replace(task, limits=limits)
    limits['max_output_bytes'] = 1
    assert captured.limits['max_output_bytes'] == 1024
    with pytest.raises(TypeError):
        captured.limits['max_output_bytes'] = 1
    with pytest.raises(ValueError):
        replace(task, input_json='{}')


def test_runtime_principal_is_explicit_and_does_not_replace_archive_owner():
    task = request()
    facade = RecordingFacade(snapshot(task))
    principal = TaskPrincipal(
        subject='basic:alice', runtime_subject='alice', display_name='Alice', anonymous=False,
    )
    port(facade).start(principal, task)
    sent = facade.calls[0][1]
    assert (sent.id, sent.display_name, sent.anonymous) == ('alice', 'Alice', False)
    assert principal.subject == 'basic:alice'


def test_unicode_request_preserves_source_hash_and_uses_runtime_canonical_hash():
    content = {'source': '\u4e2d\u6587 \u2014 caf\u00e9'}
    task = replace(request(), input_json=canonical_bytes(content).decode('utf-8'), input_sha256=content_hash(content))
    runtime_hash = canonical_digest(content)
    assert runtime_hash != task.input_sha256
    facade = RecordingFacade(snapshot(task, input_sha256=runtime_hash))
    value = port(facade).start(PRINCIPAL, task)
    assert facade.calls[0][2].input_sha256 == runtime_hash
    assert value.input_sha256 == runtime_hash
    assert value.source_input_sha256 == task.input_sha256


def test_unicode_result_retains_the_actual_runtime_output_digest():
    task = request()
    content = {'summary': '\u4e2d\u6587 \u2014 caf\u00e9'}
    actual = result(task, content=content, output_sha256=canonical_digest(content))
    value = port(RecordingFacade(actual)).result(PRINCIPAL, task, 'run-fixed')
    assert value.content_json == canonical_json(content).decode('utf-8')
    assert value.output_sha256 == actual.output_sha256
    assert value.source_input_sha256 == task.input_sha256
