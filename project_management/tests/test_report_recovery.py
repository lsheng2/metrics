from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from project_management.app.api import ProjectActor, reports as report_api
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command, draft_selection


CLIENT_ID = '91000000-0000-4000-8000-000000000001'


def setup_recovery(tmp_path):
    archive = DraftArchive(tmp_path / 'archive')
    drafts = report_api.ReportDraftService(
        archive, StaticSourceReader(source_commit=archive.repository.head(), rule_hash=archive.stage.definition_hash),
        report_api.ReportRenderer(), clock=FixedClock(),
    )
    args = archive.actor, archive.project.id, archive.stage.id
    draft = drafts.create_authored(
        *args, command_id=draft_command(21001), selection=draft_selection(),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    service = report_api.ReportRecoveryService(drafts)
    request = {
        'client_id': CLIENT_ID, 'sequence': 1, 'base_revision': draft.revision,
        'base_revision_hash': draft.revision_hash, 'snapshot_hash': draft.snapshot_hash,
        'template_hash': draft.template_definition.template_hash,
        'content': {'edits': [{
            'edit_id': '92000000-0000-4000-8000-000000000001', 'kind': 'note',
            'target': {'scope': 'report'}, 'fragment': plain_text_fragment('Recover this note.'),
            'expected_original_hash': None, 'reference_receipts': [], 'assist_receipt_id': None,
        }], 'continuity_changes': [], 'save_request': None},
    }
    return archive, drafts, draft, service, (*args, draft.draft_id), request


def test_checkpoint_survives_service_recreation_without_saving_a_revision(tmp_path):
    archive, drafts, draft, recovery, args, request = setup_recovery(tmp_path)
    head = archive.repository.head()
    receipt = recovery.put(*args, **request)
    reopened = report_api.ReportRecoveryService(drafts).get(*args, CLIENT_ID)
    assert receipt['restorable']
    assert reopened['content']['edits'][0]['fragment']['blocks'][0]['content'][0]['text'] == 'Recover this note.'
    assert reopened['base_revision_hash'] == draft.revision_hash
    assert drafts.get(*args).revision == 1
    assert archive.repository.head() == head
    assert len(recovery.list(*args)) == 1


def test_checkpoint_sequence_replay_and_discard_cannot_erase_a_newer_buffer(tmp_path):
    _, _, _, recovery, args, request = setup_recovery(tmp_path)
    first = recovery.put(*args, **request)
    assert recovery.put(*args, **request) == first
    changed = deepcopy(request)
    changed['content']['edits'][0]['fragment'] = plain_text_fragment('Newer content.')
    with pytest.raises(report_api.ReportError):
        recovery.put(*args, **changed)
    changed['sequence'] = 2
    recovery.put(*args, **changed)
    with pytest.raises(report_api.ReportError):
        recovery.discard(*args, CLIENT_ID, expected_sequence=1)
    with pytest.raises(report_api.ReportError):
        recovery.put(*args, **request)
    assert recovery.get(*args, CLIENT_ID)['sequence'] == 2
    recovery.discard(*args, CLIENT_ID, expected_sequence=2)
    assert recovery.list(*args) == ()


def test_advanced_revision_retains_checkpoint_for_manual_reconciliation(tmp_path):
    _, drafts, draft, recovery, args, request = setup_recovery(tmp_path)
    recovery.put(*args, **request)
    drafts.save_authored(
        *args, command_id=draft_command(21002), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash, edits=(),
    )
    value = recovery.get(*args, CLIENT_ID)
    assert not value['restorable']
    assert value['content']['edits']
    assert drafts.get(*args).revision == 2


@pytest.mark.parametrize('mutation', ['owner', 'hash', 'path', 'fields', 'fragment', 'oversize', 'target'])
def test_checkpoint_rejects_untrusted_binding_and_content(tmp_path, mutation):
    _, _, _, recovery, args, request = setup_recovery(tmp_path)
    if mutation == 'owner':
        args = (ProjectActor('different-owner'), *args[1:])
    elif mutation == 'hash':
        request['base_revision_hash'] = '0' * 64
    elif mutation == 'path':
        request['client_id'] = '../escape'
    elif mutation == 'fields':
        request['content']['csrfmiddlewaretoken'] = 'not-for-storage'
    elif mutation == 'fragment':
        request['content']['edits'][0]['fragment'] = {'schema_version': 2, 'blocks': [{'type': 'script', 'text': 'evil'}]}
    elif mutation == 'target':
        request['content']['edits'][0]['target'] = {'scope': 'daily_note', 'note_id': CLIENT_ID}
    else:
        request['content']['edits'][0]['fragment'] = plain_text_fragment('x' * 1_048_577)
    with pytest.raises(report_api.ReportError):
        recovery.put(*args, **request)


def test_expired_checkpoint_is_not_restorable_and_unknown_save_is_retained(tmp_path):
    _, drafts, draft, recovery, args, request = setup_recovery(tmp_path)
    request['content']['save_request'] = {
        'command_id': draft_command(21003), 'expected_revision': 1,
        'expected_revision_hash': draft.revision_hash,
        'edits': deepcopy(request['content']['edits']), 'continuity_changes': [],
    }
    recovery.put(*args, **request)
    value = recovery.get(*args, CLIENT_ID)
    assert value['content']['save_request']['command_id'] == draft_command(21003)
    now = datetime.fromisoformat(value['saved_at']) + timedelta(days=8)
    drafts.clock = lambda: now.astimezone(UTC)
    expired = recovery.get(*args, CLIENT_ID)
    assert expired['expired'] and not expired['restorable']
    assert drafts.get(*args).revision == 1


def test_independent_tabs_are_bounded_and_cannot_replace_each_others_checkpoint(tmp_path):
    _, _, _, recovery, args, request = setup_recovery(tmp_path)
    for index in range(1, 5):
        recovery.put(*args, **{**request, 'client_id': f'91000000-0000-4000-8000-{index:012d}'})
    with pytest.raises(report_api.ReportError) as limit:
        recovery.put(*args, **{**request, 'client_id': '91000000-0000-4000-8000-000000000005'})
    assert limit.value.code == 'REPORT_LIMIT'
    assert len(recovery.list(*args)) == 4
    recovery.discard(*args, CLIENT_ID, expected_sequence=1)
    assert len(recovery.list(*args)) == 3


def test_corrupt_checkpoint_is_not_offered_as_valid_recovery(tmp_path):
    from project_management.storage.paths import write_bytes
    archive, _, draft, recovery, args, request = setup_recovery(tmp_path)
    recovery.put(*args, **request)
    root = archive.repository.runtime / 'report-drafts' / draft.draft_id
    write_bytes(root, f'recovery/{CLIENT_ID}.json', b'{"payload":{},"sha256":"invalid"}')
    with pytest.raises(report_api.ReportError) as invalid:
        recovery.get(*args, CLIENT_ID)
    assert invalid.value.code == 'REPORT_ARTIFACT_INVALID'
