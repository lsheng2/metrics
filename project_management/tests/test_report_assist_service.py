import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ai_base_application_sdk import TaskRunClient
import httpx
import pytest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_assists import available_targets
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.out.report_ai_task import AuthoringTaskContract
from project_management.services.report_assist_wire import wire_attempt
from project_management.services.report_assist_wire import make_intent
from project_management.storage.report_assists import ReportAssistStore
from project_management.app.domain.report_assists import build_assist_input
from project_management.tests.report_draft_fixtures import DraftArchive, StaticSourceReader, draft_selection
from project_management.tests.summary_fixtures import PACK_ROOT, SummaryScenario
from project_management.app.api.reports import AuthoringTemplateSelection, ReportDraftService, ReportRenderer


@pytest.fixture
def assist_environment(tmp_path):
    return make_assist_environment(tmp_path)


def make_assist_environment(tmp_path, *, actor_subject='archive-owner', draft_service=None, draft=None):
    if draft_service is None:
        from project_management.app.api import ProjectActor
        archive = DraftArchive(tmp_path)
        archive.actor = ProjectActor(actor_subject)
        archive.repository.owner_subject = actor_subject
        draft_service = ReportDraftService(archive, StaticSourceReader(rule_hash=archive.stage.definition_hash), ReportRenderer())
        draft = draft_service.create_authored(
            archive.actor, archive.project.id, archive.stage.id, command_id=str(uuid4()),
            selection=draft_selection(), template=AuthoringTemplateSelection('builtin', 'daily-standup', '2'),
        )
    else:
        archive = draft_service.archive
    contract = AuthoringTaskContract.load(PACK_ROOT)
    backend = AiBackendTarget('http://127.0.0.1:18888', 'metrics-dashboard', 'store-fixture',
                              f'projects.{archive.project.id}.stages.{archive.stage.id}', 'grant-1', 'policy-1')
    requests = []
    state = {'attempt': None, 'drop_submit': False}

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == 'POST' and request.url.path == '/api/runs':
            state['assist_id'] = json.loads(request.content)['clientRunKey']
        service = state['service']
        intent = service._read_intent(archive.actor, archive.project.id, archive.stage.id, draft.draft_id, state['assist_id'])
        attempt = wire_attempt(intent, contract)
        source = json.loads(attempt.prepared.input_content)
        output = {'schema_version': 1, 'targets': [{
            'target_id': row['target_id'], 'status': 'filled', 'fragment': plain_text_fragment('Review the validation result.'),
            'evidence_refs': [next(item['ref_id'] for item in source['evidence']
                                   if row['source_key'] is None or item['source_key'] == row['source_key'])],
            'reason_code': None,
        } for row in source['targets']]}
        snapshot, result = SummaryScenario.responses(SimpleNamespace(), attempt, output)
        if request.method == 'POST' and state['drop_submit']:
            state['drop_submit'] = False
            raise httpx.ReadTimeout('Synthetic lost submit response', request=request)
        if state.get('response_hook'):
            return state['response_hook'](request, snapshot, result)
        if request.url.path.endswith('/cancel'):
            snapshot.update(state='canceled')
            snapshot['result'] = {'availability': 'not_produced', 'sha256': None, 'mediaType': None, 'expiresAt': None}
            return httpx.Response(200, json={'contractVersion': 'task-run/1', 'cancelApplied': True, 'run': snapshot})
        return httpx.Response(200, json=result if request.url.path.endswith('/result') else snapshot)

    def client(target):
        return TaskRunClient(base_url=target.base_url, source_app_id=target.source_app_id,
                             run_store_id=target.run_store_id, credential_ref='synthetic-only', token='synthetic-only',
                             transport=httpx.MockTransport(handler))

    cls = importlib.import_module('project_management.services.report_assists').ReportAssistService
    service = cls(draft_service, contract, backend=backend, client_factory=client)
    state['service'] = service
    command = str(uuid4())
    state['assist_id'] = service.assist_id_for(draft.draft_id, command)
    target = next(item for item in available_targets(draft) if item.target == {'scope': 'report'})
    return SimpleNamespace(archive=archive, drafts=draft_service, draft=draft, service=service, state=state,
                           command=command, target=target, requests=requests)


def submit(env, **changes):
    values = {
        'command_id': env.command, 'expected_revision': env.draft.revision,
        'expected_revision_hash': env.draft.revision_hash,
        'target_ids': (env.target.target_id,), 'instruction': 'Summarize the next action.',
    }
    values.update(changes)
    return env.service.submit(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, **values)


def test_shouldPersistOneCandidateAndReplayWithoutAnotherSubmit(assist_environment):
    env = assist_environment
    status = submit(env)
    assert status.state == 'candidate_ready'
    assert submit(env).assist_id == status.assist_id
    assert len([item for item in env.requests if item[0] == 'POST']) == 1
    original = env.drafts.get(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id)
    assert original.revision == 1
    assert original.authored_edits == ()
    with pytest.raises(ReportError):
        submit(env, instruction='A different instruction.')


def test_shouldRecoverUnknownSubmitByOriginalKey(assist_environment):
    env = assist_environment
    env.state['drop_submit'] = True
    first = submit(env)
    assert first.state == 'unknown'
    second = env.service.observe(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id, first.assist_id)
    assert second.state == 'candidate_ready'
    assert [item[0] for item in env.requests] == ['POST', 'GET', 'GET']
    assert env.requests[1][1] == '/api/runs/by-client-key'


def test_shouldRefuseStaleDraftBeforeAnyNetwork(assist_environment):
    env = assist_environment
    with pytest.raises(ReportError) as caught:
        submit(env, expected_revision=2)
    assert caught.value.code == 'REPORT_REVISION_CONFLICT'
    assert env.requests == []


def test_shouldCancelCandidateBeforeItCanBeAppliedOrSaved(assist_environment):
    env = assist_environment
    ready = submit(env)
    canceled = env.service.cancel(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                 env.draft.draft_id, ready.assist_id, command_id=str(uuid4()))
    assert canceled.state == 'canceled'
    with pytest.raises(ReportError):
        env.service.candidate(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                              env.draft.draft_id, ready.assist_id)


def test_shouldVerifyCandidateOnSaveAndRetainProvenanceAfterHumanEdit(assist_environment):
    env = assist_environment
    verifier = importlib.import_module('project_management.services.report_assist_receipts').ReportAssistReceiptVerifier
    env.drafts.assist_verifier = verifier(env.service.contract)
    ready = submit(env)
    candidate = env.service.candidate(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                      env.draft.draft_id, ready.assist_id)
    edit = AuthoredEditRequest(str(uuid4()), 'note', {'scope': 'report'}, candidate['targets'][0]['fragment'],
                               assist_receipt_id=ready.assist_id)
    saved = env.drafts.save_authored(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                     env.draft.draft_id, command_id=str(uuid4()),
                                     expected_revision=1, expected_revision_hash=env.draft.revision_hash, edits=(edit,))
    assert saved.authored_edits[0].origin == 'ai_assisted'
    reference = saved.authored_edits[0].source_ai_result_ref
    assert reference['assist_id'] == ready.assist_id
    from dataclasses import replace
    manual = replace(edit, fragment=plain_text_fragment('Human revised the AI note.'), assist_receipt_id=None)
    revised = env.drafts.save_authored(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                       env.draft.draft_id, command_id=str(uuid4()),
                                       expected_revision=2, expected_revision_hash=saved.revision_hash, edits=(manual,))
    assert revised.authored_edits[0].origin == 'human'
    assert revised.authored_edits[0].source_ai_result_ref == reference


def test_shouldRejectForgedOrCanceledReceiptOnSave(assist_environment):
    env = assist_environment
    verifier = importlib.import_module('project_management.services.report_assist_receipts').ReportAssistReceiptVerifier
    env.drafts.assist_verifier = verifier(env.service.contract)
    ready = submit(env)
    env.service.cancel(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                       env.draft.draft_id, ready.assist_id, command_id=str(uuid4()))
    edit = AuthoredEditRequest(str(uuid4()), 'note', {'scope': 'report'}, plain_text_fragment('Altered candidate.'),
                               assist_receipt_id=ready.assist_id)
    with pytest.raises(ReportError):
        env.drafts.save_authored(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                 env.draft.draft_id, command_id=str(uuid4()), expected_revision=1,
                                 expected_revision_hash=env.draft.revision_hash, edits=(edit,))
    assert env.drafts.get(env.archive.actor, env.archive.project.id, env.archive.stage.id, env.draft.draft_id).revision == 1


@pytest.mark.parametrize('dispatched', (False, True))
def test_shouldResumeCrashWithoutLosingOriginalDispatchDecision(assist_environment, dispatched):
    env = assist_environment
    value = build_assist_input(env.draft, (env.target.target_id,), 'Summarize the next action.')
    intent = make_intent(env.draft, env.command, value, env.service.contract, env.service.backend, env.service.clock())
    with env.archive._report_repository(env.archive.actor, env.archive.project.id, env.archive.stage.id, write=True) as repo:
        store = ReportAssistStore(repo)
        store.write(intent['assist_id'], 'intent', intent)
        store.set_active(env.draft.draft_id, intent['assist_id'])
        if dispatched:
            store.write(intent['assist_id'], 'dispatch', {'input_hash': intent['input_hash']})
    if dispatched:
        result = env.service.observe(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                     env.draft.draft_id, intent['assist_id'])
    else:
        result = submit(env)
    assert result.state == 'candidate_ready'
    assert env.requests[0][0] == ('GET' if dispatched else 'POST')
    restored = env.service._read_intent(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                       env.draft.draft_id, intent['assist_id'])
    assert restored['request'] == intent['request']
