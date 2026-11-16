from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib

import pytest

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.task_runs import (
    TaskDispatch, TaskPrincipal, TaskResultSummary, TaskRunRequest, TaskRunResult, TaskRunSnapshot,
)
from project_management.app.domain.task_run_codec import (
    principal_from_record, request_from_record, result_from_record, snapshot_from_record,
)


def task():
    return TaskRunRequest(
        profile_id='metrics.project_summary', profile_version='1',
        profile_definition_sha256='a' * 64, output_schema_sha256='b' * 64,
        input_json='{}', input_sha256=content_hash({}), client_run_key='key-1',
        deadline_at=datetime.now(UTC) + timedelta(minutes=1), limits={'max_output_bytes': 1024},
        minimum_result_retention_seconds=60,
    )


def test_request_roundtrip_preserves_exact_deadline_key_and_input():
    expected = task()
    assert request_from_record(decode_json(canonical_bytes(expected))) == expected


def test_principal_roundtrip_does_not_infer_anonymous_state():
    expected = TaskPrincipal(
        subject='local_operator', runtime_subject='local_operator', display_name='Local operator', anonymous=True,
    )
    assert principal_from_record(decode_json(canonical_bytes(expected))) == expected
    with pytest.raises(ValueError):
        principal_from_record({'subject': 'local_operator', 'display_name': 'Local operator'})
    with pytest.raises(ValueError):
        principal_from_record({'subject': 'local_operator', 'display_name': 'Local operator', 'anonymous': True})


@pytest.mark.parametrize('mutation', ['old-wire', 'missing', 'extra', 'naive-deadline', 'input-drift'])
def test_request_reader_rejects_legacy_or_incomplete_records(mutation):
    data = decode_json(canonical_bytes(task()))
    if mutation == 'old-wire':
        data = {'contractVersion': 'task-run/1', 'deadlineAt': data['deadline_at']}
    elif mutation == 'missing':
        data.pop('correlation_id')
    elif mutation == 'extra':
        data['backend'] = {'scopeKey': 'old'}
    elif mutation == 'naive-deadline':
        data['deadline_at'] = '2026-11-16T12:00:00'
    else:
        data['input_json'] = '{"changed":true}'
    with pytest.raises(ValueError):
        request_from_record(data)


def test_snapshot_reader_rebuilds_owned_types_and_preserves_uncertainty():
    expected = TaskRunSnapshot(
        run_id='run-1', profile_id=task().profile_id, profile_version='1', status='running',
        input_sha256=content_hash({}), effective_input_sha256=None,
        source_input_sha256=content_hash({}),
        dispatch=TaskDispatch(
            provider='openai-compatible', model='scripted', runtime_version='0.1.0',
            profile_definition_sha256='a' * 64, tool_definition_sha256=None,
            dispatched=False, uncertainty='unknown', usage=None,
        ),
        result=TaskResultSummary(output_sha256=None, output_schema_sha256=None, usage=None),
        error_code=None, retry=None,
    )
    assert snapshot_from_record(decode_json(canonical_bytes(expected))) == expected
    invalid = decode_json(canonical_bytes(expected))
    invalid['acceptedAt'] = '2026-11-16T00:00:00Z'
    with pytest.raises(ValueError):
        snapshot_from_record(invalid)
    incomplete = decode_json(canonical_bytes(expected))
    incomplete.pop('source_input_sha256')
    with pytest.raises(ValueError):
        snapshot_from_record(incomplete)


def test_result_record_preserves_runtime_bytes_and_distinct_source_digest():
    raw = b'{"summary":"\\u4e2d\\u6587"}'
    result = TaskRunResult(
        run_id='run-1', profile_id=task().profile_id, profile_version='1', status='succeeded',
        source_input_sha256='a' * 64, input_sha256='b' * 64, effective_input_sha256='c' * 64,
        output_schema_sha256='d' * 64, output_sha256=hashlib.sha256(raw).hexdigest(),
        content_json=raw.decode('utf-8'),
        dispatch=TaskDispatch(
            provider='openai-compatible', model='scripted', runtime_version='0.1.1.dev1',
            profile_definition_sha256='a' * 64, tool_definition_sha256=None,
            dispatched=True, uncertainty='dispatched', usage=None,
        ),
        usage=None, error_code=None, retry=None,
    )
    restored = result_from_record(decode_json(canonical_bytes(result)))
    assert restored == result
    assert restored.content_json.encode('utf-8') == raw
    assert restored.source_input_sha256 != restored.input_sha256
    with pytest.raises(ValueError):
        replace(restored, content_json=canonical_bytes(decode_json(raw)).decode('utf-8'))
