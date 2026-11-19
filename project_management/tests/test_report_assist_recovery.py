from dataclasses import replace
from uuid import uuid4

import pytest

from project_management.app.api import report_factories
from project_management.app.domain.report_assists import MAX_OBSERVATIONS
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.task_runs import TaskRunCancellation, TaskRunError
from project_management.storage.report_assists import ReportAssistStore
from project_management.tests.test_report_assist_service import assist_environment, submit


def test_shouldBuildAndSaveManualReportWhenAuthoringProfileCannotLoad(assist_environment, monkeypatch):
    env = assist_environment

    def missing():
        raise AnalysisError('ANALYSIS_CONTRACT_INVALID')

    monkeypatch.setattr(report_factories, '_authoring_contract', missing)
    manual = report_factories.build_report_service(project_api=object(), archive=env.archive, contract=object())
    saved = manual.save_authored(
        env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id,
        command_id=str(uuid4()), expected_revision=1, expected_revision_hash=env.draft.revision_hash,
        edits=(AuthoredEditRequest(str(uuid4()), 'note', {'scope': 'report'}, plain_text_fragment('Manual note.')),),
    )
    assert saved.revision == 2
    with pytest.raises(ReportError) as unavailable:
        report_factories.build_report_assist_service(draft_service=manual)
    assert unavailable.value.code == 'REPORT_AI_UNAVAILABLE'
    assert env.requests == []


@pytest.mark.parametrize('case', ('invalid_result', 'stale', 'rejected'))
def test_shouldSettleDefiniteFailureWithoutReleasingUnknownExposure(assist_environment, case):
    env = assist_environment

    def response(method, snapshot, result):
        if case == 'rejected':
            raise TaskRunError('input_schema_invalid', retry='correct')
        if method == 'result':
            if case == 'invalid_result':
                return replace(result, output_schema_sha256='0' * 64)
            env.drafts.save_authored(
                env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id,
                command_id=str(uuid4()), expected_revision=1, expected_revision_hash=env.draft.revision_hash,
                edits=(AuthoredEditRequest(str(uuid4()), 'note', {'scope': 'report'},
                                           plain_text_fragment('New manual content.')),),
            )
            return result
        return snapshot

    env.state['response_hook'] = response
    result = submit(env)
    assert result.state == 'failed'
    env.state.pop('response_hook')
    current = env.drafts.get(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id)
    ready = submit(env, command_id=str(uuid4()), expected_revision=current.revision,
                   expected_revision_hash=current.revision_hash)
    assert ready.state == 'candidate_ready'


def test_shouldKeepUnverifiedRuntimeBindingUnknown(assist_environment):
    env = assist_environment
    env.state['response_hook'] = lambda method, snapshot, result: replace(snapshot, profile_version='wrong-version')
    unknown = submit(env)
    assert unknown.state == 'unknown'
    with pytest.raises(ReportError) as busy:
        submit(env, command_id=str(uuid4()))
    assert busy.value.code == 'REPORT_AI_BUSY'
    assert len(env.requests) == 1


def test_shouldObserveCanceledRequestUntilRemoteExposureIsSettled(assist_environment):
    env = assist_environment
    env.state['drop_submit'] = True
    started = submit(env)

    def response(method, snapshot, result):
        if method == 'cancel':
            return TaskRunCancellation(run_id=snapshot.run_id, canceled=True)
        return replace(snapshot, status='indeterminate', dispatch=replace(snapshot.dispatch, uncertainty='unknown'))

    env.state['response_hook'] = response
    args = (env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, started.assist_id)
    requested = env.service.cancel(*args, command_id=str(uuid4()))
    assert requested.state == 'cancel_requested'
    env.state.pop('response_hook')
    settled = env.service.observe(*args)
    assert settled.state == 'canceled'
    with pytest.raises(ReportError) as canceled:
        env.service.candidate(*args)
    assert canceled.value.code == 'REPORT_AI_CANCELED'
    assert env.requests[-1][0] == 'get'
    assert not any(method == 'result' for method, _ in env.requests)


def test_unknown_cancel_never_admits_when_lookup_has_no_row(assist_environment):
    env = assist_environment
    env.state['drop_submit'] = True
    started = submit(env)
    env.state['absent_lookup'] = True
    args = (env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, started.assist_id)
    result = env.service.cancel(*args, command_id=str(uuid4()))
    assert result.state == 'cancel_requested'
    assert env.service.observe(*args).state == 'cancel_requested'
    assert [method for method, _ in env.requests] == ['start', 'lookup', 'lookup']


def test_shouldBoundObservationIoBeforeCallingSdkAgain(assist_environment):
    env = assist_environment
    env.state['drop_submit'] = True
    started = submit(env)
    env.state['response_hook'] = lambda method, snapshot, result: replace(
        snapshot, status='indeterminate', dispatch=replace(snapshot.dispatch, uncertainty='unknown'),
    )
    args = (env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, started.assist_id)
    for _ in range(MAX_OBSERVATIONS + 2):
        observed = env.service.observe(*args)
    assert observed.state == 'unknown'
    assert observed.error_code == 'REPORT_AI_LIMIT'
    assert len(env.requests) <= MAX_OBSERVATIONS


def test_shouldAcceptLastAdmittedResultAndCancelWithoutExtraObservation(assist_environment):
    env = assist_environment

    def no_result(method, snapshot, result):
        if method == 'result':
            raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')
        return snapshot

    env.state['response_hook'] = no_result
    started = submit(env)
    args = (env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, started.assist_id)
    for _ in range(MAX_OBSERVATIONS - 2):
        assert env.service.observe(*args).state == 'observing'
    env.state.pop('response_hook')
    assert env.service.observe(*args).state == 'candidate_ready'
    before = len(env.requests)
    assert env.service.cancel(*args, command_id=str(uuid4())).state == 'canceled'
    assert len(env.requests) == before


def test_shouldFailClosedOnMalformedStoredActivePointer(assist_environment):
    env = assist_environment
    with env.archive._report_repository(env.archive.actor, env.archive.project.id, env.archive.stage.id, write=True) as repo:
        ReportAssistStore(repo).write(env.draft.draft_id, 'active', {})
    with pytest.raises(ReportError) as invalid:
        env.service.describe(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id)
    assert invalid.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.parametrize('field,value', (
    ('snapshot', {'state': 'succeeded'}),
    ('cancel', {'run_id': 'run-fixture', 'canceled': 'yes'}),
))
def test_malformed_typed_observation_has_a_report_error(assist_environment, field, value):
    env = assist_environment
    ready = submit(env)
    with env.archive._report_repository(env.archive.actor, env.archive.project.id, env.archive.stage.id, write=True) as repo:
        store = ReportAssistStore(repo)
        observation = store.read(ready.assist_id, 'observation-00')
        store.write(ready.assist_id, 'observation-00', {**observation, field: value}, immutable=False)
    with pytest.raises(ReportError) as invalid:
        env.service.describe(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id)
    assert invalid.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.parametrize('name,value', (
    ('observation-00', {'state': []}),
    ('exchange-00', {'operation': []}),
))
def test_shouldReturnStructuredErrorForMalformedStoredStateTypes(assist_environment, name, value):
    env = assist_environment
    with env.archive._report_repository(env.archive.actor, env.archive.project.id, env.archive.stage.id, write=True) as repo:
        store = ReportAssistStore(repo)
        assist_id = str(uuid4())
        store.write(assist_id, name, value)
        with pytest.raises(ReportError) as invalid:
            store.exchange_count(assist_id)
        assert invalid.value.code == 'REPORT_ARTIFACT_INVALID'
