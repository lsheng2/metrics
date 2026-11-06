import hashlib

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.report_publication_validation import PublicationValidationContext, validate_publication_files
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command, draft_root, draft_selection


def build_service(environment):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def authored_note(value, text):
    return report_api.AuthoredEditRequest(
        f'70000000-0000-4000-8000-{value:012d}',
        'note',
        {'scope': 'report'},
        {
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [{
                    'type': 'text',
                    'text': text,
                    'marks': [],
                    'foreground': None,
                    'background': None,
                }],
            }],
        },
        None,
    )


def authored_template():
    return report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {})


def test_should_reject_schema2_packet_when_selected_history_hash_differs_from_manifest_hash_directly(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service, publication, draft = finalized_schema2_packet(environment, fail_append=False)
    files = {
        name: environment.repository.read_file(f'report_publications/{publication.manifest.publication_id}/{name}')
        for name in ('snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt', 'manifest.json')
    }
    files = corrupt_selected_history_payload(files)

    with pytest.raises(report_api.ReportError) as error:
        validate_publication_files(publication.manifest.publication_id, files, context(environment), environment.actor.subject)

    assert draft.revision == 2
    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_reject_schema2_recovery_before_append_when_selected_history_hash_differs_from_manifest_hash(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service, publication, draft = finalized_schema2_packet(environment, fail_append=True)
    before_head = environment.repository.head()
    packet = draft_root(environment, draft.draft_id) / 'finalization-files' / publication['publication_id']
    runtime_files = {path.name: path.read_bytes() for path in packet.iterdir()}
    runtime_files = corrupt_selected_history_payload(runtime_files)
    for name, data in runtime_files.items():
        (packet / name).write_bytes(data)
    intent_path = draft_root(environment, draft.draft_id) / 'finalization.json'
    intent = decode_json(intent_path.read_bytes())
    for name, data in runtime_files.items():
        intent['file_hashes'][name] = _hash(data)
        intent['file_sizes'][name] = len(data)
    intent['edits_hash'] = decode_json(runtime_files['manifest.json'])['edits_hash']
    intent_path.write_bytes(canonical_bytes(intent))

    with pytest.raises(report_api.ReportError) as error:
        service.resume_finalization(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(602),
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert environment.repository.head() == before_head
    assert environment.repository.list_files('report_publications') == ()


def finalized_schema2_packet(environment, *, fail_append):
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(600),
        selection=draft_selection(),
        template=authored_template(),
    )
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(601),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(authored_note(1, 'Original selected payload text'),),
    )
    if fail_append:
        environment.repository.fail_append_once = True
        with pytest.raises(report_api.ReportError):
            service.finalize_and_commit(
                environment.actor,
                environment.project.id,
                environment.stage.id,
                draft.draft_id,
                command_id=draft_command(602),
                expected_revision=saved.revision,
            )
        return service, decode_json((draft_root(environment, draft.draft_id) / 'finalization.json').read_bytes()), saved
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(602),
        expected_revision=saved.revision,
    )
    return service, publication, saved


def corrupt_selected_history_payload(files):
    edits = decode_json(files['edits.json'])
    selected = edits['revisions'][-1]
    selected['payload']['edits'][0]['fragment']['blocks'][0]['content'][0]['text'] = 'Self-consistently changed final payload'
    selected['revision_hash'] = _hash(canonical_bytes(selected['payload']))
    files = dict(files)
    files['edits.json'] = canonical_bytes(edits)
    manifest = decode_json(files['manifest.json'])
    manifest['edits_hash'] = _hash(files['edits.json'])
    manifest['file_hashes']['edits.json'] = manifest['edits_hash']
    files['manifest.json'] = canonical_bytes(manifest)
    return files


def context(environment):
    return PublicationValidationContext(
        environment.project.id,
        environment.stage.id,
        environment.actor.subject,
        environment.stage.definition_hash,
    )


def _hash(data):
    return hashlib.sha256(data).hexdigest()
