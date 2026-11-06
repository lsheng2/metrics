from uuid import uuid4

from ai_base_application_sdk import TaskRunClientError
import httpx
import pytest

from project_management.app.api import report_factories
from project_management.app.domain.report_assists import MAX_OBSERVATIONS
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisError
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

    def response(request, snapshot, result):
        if case == 'rejected':
            raise TaskRunClientError('invalid_request', 'correct_request', status=422)
        if request.url.path.endswith('/result'):
            if case == 'invalid_result':
                return httpx.Response(200, json={**result, 'sha256': '0' * 64})
            env.drafts.save_authored(
                env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id,
                command_id=str(uuid4()), expected_revision=1, expected_revision_hash=env.draft.revision_hash,
                edits=(AuthoredEditRequest(str(uuid4()), 'note', {'scope': 'report'},
                                           plain_text_fragment('New manual content.')),),
            )
            return httpx.Response(200, json=result)
        return httpx.Response(200, json=snapshot)

    env.state['response_hook'] = response
    result = submit(env)
    assert result.state == 'failed'
    env.state.pop('response_hook')
    current = env.drafts.get(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id)
    ready = submit(env, command_id=str(uuid4()), expected_revision=current.revision,
                   expected_revision_hash=current.revision_hash)
    assert ready.state == 'candidate_ready'


def test_shouldKeepUnverifiedStoreIdentityUnknown(assist_environment):
    env = assist_environment
    env.state['response_hook'] = lambda request, snapshot, result: httpx.Response(
        200, json={**snapshot, 'runStoreId': 'wrong-store'},
    )
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

    def response(request, snapshot, result):
        snapshot = {
            **snapshot, 'state': 'indeterminate', 'terminalAt': None, 'unresolvedExposure': True,
            'dispatch': {'attemptCount': 1, 'knowledge': 'may_have_dispatched', 'remoteStop': 'unknown'},
            'result': {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None},
        }
        if request.url.path.endswith('/cancel'):
            return httpx.Response(200, json={
                'contractVersion': 'task-run/1', 'cancelApplied': True, 'run': snapshot,
            })
        return httpx.Response(200, json=snapshot)

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
    assert env.requests[-1][0] == 'GET'
    assert not any(path.endswith('/result') for _, path in env.requests)


def test_shouldBoundObservationIoBeforeCallingSdkAgain(assist_environment):
    env = assist_environment
    env.state['drop_submit'] = True
    started = submit(env)
    env.state['response_hook'] = lambda request, snapshot, result: httpx.Response(
        200, json={**snapshot, 'state': 'indeterminate', 'terminalAt': None, 'unresolvedExposure': True},
    )
    args = (env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, started.assist_id)
    for _ in range(MAX_OBSERVATIONS + 2):
        observed = env.service.observe(*args)
    assert observed.state == 'unknown'
    assert observed.error_code == 'REPORT_AI_LIMIT'
    assert len(env.requests) <= MAX_OBSERVATIONS


def test_shouldAcceptLastAdmittedResultAndCancelWithoutExtraObservation(assist_environment):
    env = assist_environment

    def no_result(request, snapshot, result):
        if request.url.path.endswith('/result'):
            raise httpx.ReadTimeout('Synthetic result timeout', request=request)
        return httpx.Response(200, json=snapshot)

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
