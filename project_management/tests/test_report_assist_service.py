import importlib
import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from project_management.app.domain.report_assists import available_targets
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.domain.task_runs import TaskPrincipal, TaskRunCancellation, TaskRunError
from project_management.services.task_contracts import AuthoringTaskContract
from project_management.services.report_assist_records import make_intent, read_assist_attempt
from project_management.storage.report_assists import ReportAssistStore
from project_management.app.domain.report_assists import build_assist_input
from project_management.tests.report_draft_fixtures import DraftArchive, StaticSourceReader, draft_selection
from project_management.tests.summary_fixtures import SummaryScenario
from project_management.app.api.reports import AuthoringTemplateSelection, ReportDraftService, ReportRenderer


@pytest.fixture
def assist_environment(tmp_path):
    return make_assist_environment(tmp_path)


class AssistPort:
    def __init__(self, handler):
        self.handler = handler

    def start(self, principal, request):
        return self.handler('start', principal, request, None)

    def lookup(self, principal, request):
        return self.handler('lookup', principal, request, None)

    def get(self, principal, request, run_id):
        return self.handler('get', principal, request, run_id)

    def result(self, principal, request, run_id):
        return self.handler('result', principal, request, run_id)

    def cancel(self, principal, run_id):
        return self.handler('cancel', principal, None, run_id)


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
    contract = AuthoringTaskContract(load_task_profile('metrics.report_authoring'))
    requests = []
    state = {'drop_submit': False, 'request_values': []}

    def handler(method, principal, request, run_id):
        assert principal.subject == archive.actor.subject
        requests.append((method, run_id))
        state['request_values'].append((method, request))
        if method == 'start':
            state['assist_id'] = request.client_run_key
        if method == 'lookup' and state.get('absent_lookup'):
            return None
        service = state['service']
        intent = service._read_intent(archive.actor, archive.project.id, archive.stage.id, draft.draft_id, state['assist_id'])
        attempt = read_assist_attempt(intent, contract)
        source = json.loads(attempt.prepared.input_content)
        output = {'schema_version': 1, 'targets': [{
            'target_id': row['target_id'], 'status': 'filled', 'fragment': plain_text_fragment('Review the validation result.'),
            'evidence_refs': [next(item['ref_id'] for item in source['evidence']
                                   if row['source_key'] is None or item['source_key'] == row['source_key'])],
            'reason_code': None,
        } for row in source['targets']]}
        snapshot, result = SummaryScenario.responses(SimpleNamespace(), attempt, output)
        if method == 'start' and state['drop_submit']:
            state['drop_submit'] = False
            raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')
        if state.get('response_hook'):
            return state['response_hook'](method, snapshot, result)
        if method == 'cancel':
            state['canceled'] = True
            return TaskRunCancellation(run_id=run_id, canceled=True)
        if state.get('canceled'):
            snapshot = replace(snapshot, status='canceled')
        return result if method == 'result' else snapshot

    cls = importlib.import_module('project_management.services.report_assists').ReportAssistService
    principal_for = lambda actor: TaskPrincipal(
        subject=actor.subject, runtime_subject=actor.subject, display_name='Author', anonymous=False,
    )
    service = cls(draft_service, contract, task_run_port=AssistPort(handler), principal_resolver=principal_for)
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
    assert len([item for item in env.requests if item[0] == 'start']) == 1
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
    assert [item[0] for item in env.requests] == ['start', 'lookup', 'result']
    assert env.state['request_values'][0][1] == env.state['request_values'][1][1]


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
    assert reference['schema_version'] == 2
    assert 'run_store_id' not in reference
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
    intent = make_intent(env.draft, env.command, value, env.service.contract,
                         env.service.principal_resolver(env.archive.actor), env.service.clock())
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
    assert env.requests[0][0] == ('lookup' if dispatched else 'start')
    restored = env.service._read_intent(env.archive.actor, env.archive.project.id, env.archive.stage.id,
                                       env.draft.draft_id, intent['assist_id'])
    assert restored['request'] == intent['request']
