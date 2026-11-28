from dataclasses import replace
import json

import pytest

from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_input import build_initial_input
from project_management.tests.summary_fixtures import SummaryScenario
from project_management.tests.test_summary_input import body_not_requested_metadata


def values():
    scenario = SummaryScenario()
    scenario.setUp()
    prepared = scenario.prepared()
    attempt = scenario.attempt(prepared)
    output = scenario.output(prepared)
    snapshot, result = scenario.responses(attempt, output)
    return scenario.contract, attempt.request, snapshot, result, output


def test_contract_validates_new_owned_records_without_http_sdk_pack():
    contract, request, snapshot, result, output = values()
    contract.validate_request(request)
    contract.validate_snapshot(request, snapshot)
    assert contract.validate_result_envelope(request, snapshot, result) == output
    assert contract.profile_ref == 'metrics.project_summary@2'


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


def test_v2_request_preparation_admits_metadata_without_optional_body_evidence():
    scenario = SummaryScenario()
    scenario.setUp()
    reference, source = scenario.summary_source()
    retained = body_not_requested_metadata(source)
    prepared = build_initial_input(
        scenario.project.id,
        scenario.stage,
        scenario.source_key(scenario.intent()),
        reference,
        retained,
        scenario.contract.profile_ref,
    )
    attempt = scenario.attempt(prepared)
    value = json.loads(attempt.request.input_json)

    scenario.contract.validate_request(attempt.request)
    assert attempt.request.profile_version == '2'
    assert value['profile_revision'] == 'metrics.project_summary@2'
    assert [row['kind'] for row in value['evidence']] == ['field', 'comment', 'comment', 'comment']
    assert 'Attachment and linked-item bodies are not supplied' in scenario.contract.profile.instructions
    assert 'blockers and limitations must cite evidence_refs' in scenario.contract.profile.instructions
