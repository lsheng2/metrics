import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from project_management.app.domain.report_assists import available_targets
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.report_authoring_fragments import plain_text_fragment, rich_text_fragment_plain_text
from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.domain.task_runs import TaskPrincipal
from project_management.services.task_contracts import AuthoringTaskContract
from project_management.services.report_assist_receipts import ReportAssistReceiptVerifier
from project_management.services.report_assist_records import read_assist_attempt
from project_management.services.report_assists import ReportAssistService
from project_management.tests.history_persistence_fixtures import continuity_document, history_fixture, prepare_daily
from project_management.tests.summary_fixtures import SummaryScenario
from project_management.tests.test_report_assist_service import AssistPort
from project_management.tests.test_report_template_compilation import slot_block


@pytest.mark.django_db(transaction=True)
def test_shouldSaveDistinctTargetFamiliesWithoutChangingSourceOrArState(tmp_path):
    document = continuity_document()
    document['blocks'].append(slot_block(12, fill_mode='ai_optional', required=False))
    fixture = history_fixture(tmp_path, document=document)
    args = (fixture.actor, fixture.project.id, fixture.stage.id)
    day = prepare_daily(fixture, 1, '2026-11-02', None)
    drafts = fixture.draft_service
    draft = drafts.create_authored(*args, command_id=day.command_id, selection=day.selection,
                                  template=fixture.template_selection, preparation_id=day.preparation_id)
    persistent_id = str(uuid4())
    draft = drafts.save_authored(
        *args, draft.draft_id, command_id=str(uuid4()), expected_revision=1,
        expected_revision_hash=draft.revision_hash, edits=(),
        continuity_changes=({'kind': 'add_persistent_note', 'note_id': persistent_id, 'target': 'report',
                             'issue_ref': None, 'fragment': plain_text_fragment('Persistent context.'),
                             'carry_forward': True},),
    )
    offered = available_targets(draft)
    targets = [
        next(item for item in offered if item.target.get('field') == 'what'),
        next(item for item in offered if item.target['scope'] == 'template_slot'),
        next(item for item in offered if item.target['scope'] == 'persistent_note'),
        next(item for item in offered if item.target['scope'] == 'report_action'),
    ]
    contract = AuthoringTaskContract(load_task_profile('metrics.report_authoring'))
    command = str(uuid4())
    calls = []

    def response(method, principal, request, run_id):
        calls.append(method)
        intent = service._read_intent(*args, draft.draft_id, service.assist_id_for(draft.draft_id, command))
        attempt = read_assist_attempt(intent, contract)
        source = json.loads(attempt.prepared.input_content)
        output = {'schema_version': 1, 'targets': [{
            'target_id': row['target_id'], 'status': 'filled',
            'fragment': plain_text_fragment('Review the validation result.'),
            'evidence_refs': [next(item['ref_id'] for item in source['evidence']
                                   if row['source_key'] is None or item['source_key'] == row['source_key'])],
            'reason_code': None,
        } for row in source['targets']]}
        snapshot, result = SummaryScenario.responses(SimpleNamespace(), attempt, output)
        return result if method == 'result' else snapshot

    service = ReportAssistService(
        drafts, contract, task_run_port=AssistPort(response),
        principal_resolver=lambda actor: TaskPrincipal(
            subject=actor.subject, runtime_subject=actor.subject, display_name='Author', anonymous=False,
        ),
    )
    drafts.assist_verifier = ReportAssistReceiptVerifier(contract)
    ready = service.submit(*args, draft.draft_id, command_id=command, expected_revision=draft.revision,
                           expected_revision_hash=draft.revision_hash,
                           target_ids=[item.target_id for item in targets], instruction='Summarize the next action.')
    assert ready.state == 'candidate_ready'
    output = service.candidate(*args, draft.draft_id, ready.assist_id)
    fragments = {item['target_id']: item['fragment'] for item in output['targets']}
    saved = drafts.save_authored(
        *args, draft.draft_id, command_id=str(uuid4()), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=tuple(AuthoredEditRequest(str(uuid4()), item.kind, item.target, fragments[item.target_id],
                                       item.expected_original_hash, assist_receipt_id=ready.assist_id) for item in targets),
    )
    assert {edit.target['scope'] for edit in saved.authored_edits} == {
        'issue', 'template_slot', 'persistent_note', 'report_action',
    }
    assert all(edit.origin == 'ai_assisted' for edit in saved.authored_edits)
    assert all(edit.source_ai_result_ref['assist_id'] == ready.assist_id for edit in saved.authored_edits)
    assert all(rich_text_fragment_plain_text(edit.fragment) == 'Review the validation result.'
               for edit in saved.authored_edits)
    assert [row.status for row in draft.snapshot.rows] == [row.status for row in saved.snapshot.rows]
    old_action = draft.authoring_context['actions'][0]
    action = next(item for item in saved.authoring_context['actions'] if item['action_id'] == old_action['action_id'])
    assert action['owner_ref'] == old_action['owner_ref']
    assert action['tracking_state'] == old_action['tracking_state']
    assert rich_text_fragment_plain_text(action['body_fragment']) == 'Review the validation result.'
    assert saved.authoring_context['persistent_notes'][0]['provenance']['origin'] == 'ai_assisted'
    assert calls.count('start') == 1
