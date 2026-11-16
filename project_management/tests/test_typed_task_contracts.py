from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.task_runs import (
    TaskDispatch, TaskResultSummary, TaskRunResult, TaskRunSnapshot,
)
from project_management.services.task_contracts import SummaryTaskContract


def values():
    root = Path(__file__).resolve().parents[1] / 'ai_bundle/strict-summary/task-run-contract-0.1.0a2'
    source = json.loads((root / 'profiles/project-summary/input.json').read_text(encoding='utf-8'))
    output = json.loads((root / 'fixtures/project-summary/strict-summary-output-golden.json').read_text(encoding='utf-8'))
    source['profile_revision'] = output['profile_revision'] = 'metrics.project_summary@1'
    prepared = SimpleNamespace(
        input_content=canonical_bytes(source).decode('utf-8'), input_hash=content_hash(source),
    )
    contract = SummaryTaskContract(load_task_profile('metrics.project_summary'))
    request = contract.make_request(prepared, 'attempt-key', datetime.now(UTC) + timedelta(minutes=1))
    dispatch = TaskDispatch(
        provider='openai-compatible', model='scripted', runtime_version='0.1.0',
        profile_definition_sha256=contract.definition_hash, tool_definition_sha256=None,
        dispatched=True, uncertainty='dispatched', usage=None,
    )
    snapshot = TaskRunSnapshot(
        run_id='run-1', profile_id=request.profile_id, profile_version=request.profile_version,
        status='succeeded', input_sha256=request.input_sha256, effective_input_sha256=request.input_sha256,
        source_input_sha256=request.input_sha256,
        dispatch=dispatch, result=TaskResultSummary(
            output_sha256=content_hash(output), output_schema_sha256=contract.output_schema_hash, usage=None,
        ), error_code=None, retry=None,
    )
    result = TaskRunResult(
        run_id='run-1', profile_id=request.profile_id, profile_version=request.profile_version,
        status='succeeded', input_sha256=request.input_sha256, effective_input_sha256=request.input_sha256,
        source_input_sha256=request.input_sha256,
        output_schema_sha256=contract.output_schema_hash, output_sha256=content_hash(output),
        content_json=canonical_bytes(output).decode('utf-8'), dispatch=dispatch, usage=None,
        error_code=None, retry=None,
    )
    return contract, request, snapshot, result, output


def test_contract_validates_new_owned_records_without_http_sdk_pack():
    contract, request, snapshot, result, output = values()
    contract.validate_request(request)
    contract.validate_snapshot(request, snapshot)
    assert contract.validate_result_envelope(request, snapshot, result) == output
    assert contract.profile_ref == 'metrics.project_summary@1'


@pytest.mark.parametrize('field,value', [
    ('profile_id', 'metrics.report_authoring'),
    ('profile_version', 'other'),
    ('profile_definition_sha256', 'f' * 64),
    ('output_schema_sha256', 'f' * 64),
])
def test_request_cannot_change_the_pinned_business_profile(field, value):
    contract, request, _, _, _ = values()
    with pytest.raises(AnalysisError):
        contract.validate_request(replace(request, **{field: value}))


def test_uncertain_dispatch_cannot_become_an_accepted_output():
    contract, request, snapshot, result, _ = values()
    uncertain = replace(snapshot, dispatch=replace(snapshot.dispatch, uncertainty='unknown'))
    with pytest.raises(AnalysisError):
        contract.validate_result_envelope(request, uncertain, result)


@pytest.mark.parametrize('field,value', [
    ('run_id', 'other-run'),
    ('source_input_sha256', 'f' * 64),
    ('input_sha256', 'f' * 64),
    ('effective_input_sha256', 'f' * 64),
    ('output_schema_sha256', 'f' * 64),
    ('status', 'failed'),
])
def test_result_cannot_replace_another_run_or_change_its_binding(field, value):
    contract, request, snapshot, result, _ = values()
    with pytest.raises(AnalysisError):
        contract.validate_result_envelope(request, snapshot, replace(result, **{field: value}))


def test_a_rehashed_model_response_still_needs_business_output_schema():
    contract, request, snapshot, result, _ = values()
    wrong = {'kind': 'not-a-summary'}
    digest = content_hash(wrong)
    snapshot = replace(snapshot, result=replace(snapshot.result, output_sha256=digest))
    result = replace(result, content_json=canonical_bytes(wrong).decode('utf-8'), output_sha256=digest)
    with pytest.raises(AnalysisError):
        contract.validate_result_envelope(request, snapshot, result)


def test_legacy_wire_dictionary_is_not_a_new_snapshot():
    contract, request, _, _, _ = values()
    with pytest.raises(AnalysisError):
        contract.validate_snapshot(request, {'contractVersion': 'task-run/1', 'state': 'succeeded'})


def test_runtime_digest_does_not_replace_the_application_source_binding():
    contract, request, snapshot, result, output = values()
    snapshot = replace(snapshot, input_sha256='d' * 64)
    result = replace(result, input_sha256='d' * 64)
    assert contract.validate_result_envelope(request, snapshot, result) == output
    with pytest.raises(AnalysisError):
        contract.validate_snapshot(request, replace(snapshot, source_input_sha256='e' * 64))
