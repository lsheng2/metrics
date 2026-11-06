import pytest
from dataclasses import replace
import hashlib

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.storage.paths import read_bytes
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_note,
    draft_root,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template


LEGACY_DAILY_TEMPLATE_HASH = 'de8f706a0cd792ee289aab334ccfe82e1d638de3b3df5fe47179290c6b52867a'


def build_service(environment):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def builtin_template():
    return report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {})


def fragment(text):
    return {
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
    }


def authored_note(value, text):
    return report_api.AuthoredEditRequest(
        f'40000000-0000-4000-8000-{value:012d}',
        'note',
        {'scope': 'report'},
        fragment(text),
        None,
    )


def test_should_publish_schema2_exact_packet_resume_and_download_original_bytes(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(500),
        selection=draft_selection(),
        template=builtin_template(),
    )
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(501),
        expected_revision=1,
        expected_revision_hash=draft.revision_hash,
        edits=(authored_note(1, 'Schema2 retained content'),),
    )

    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        service.finalize_and_commit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(502),
            expected_revision=saved.revision,
        )
    publication = service.resume_finalization(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(502),
    )
    duplicate = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(502),
        expected_revision=saved.revision,
    )

    names = ('snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt', 'manifest.json')
    publication_root = f'report_publications/{publication.manifest.publication_id}'
    runtime_root = draft_root(environment, draft.draft_id) / 'finalization-files' / publication.manifest.publication_id
    manifest = decode_json(read_bytes(environment.repository.archive, f'{publication_root}/manifest.json'))
    intent = decode_json((draft_root(environment, draft.draft_id) / 'finalization.json').read_bytes())
    template_bytes = read_bytes(environment.repository.archive, f'{publication_root}/template.json')
    edits_bytes = read_bytes(environment.repository.archive, f'{publication_root}/edits.json')
    revision_two = decode_json((draft_root(environment, draft.draft_id) / 'revisions' / '00000002.json').read_bytes())

    assert tuple(sorted(path.name for path in runtime_root.iterdir())) == tuple(sorted(names))
    assert tuple(sorted(path.split('/')[-1] for path in environment.repository.list_files(publication_root))) == tuple(sorted(names))
    assert duplicate.manifest.publication_id == publication.manifest.publication_id
    assert duplicate.commit_id == publication.commit_id
    assert set(manifest) == {
        'schema_version', 'publication_id', 'draft_id', 'draft_revision', 'draft_revision_hash', 'purpose',
        'parent_publication_id', 'baseline_publication_id', 'source_as_of', 'finalized_at', 'finalized_by',
        'snapshot_hash', 'template_hash', 'file_hashes', 'authoring_schema', 'template_snapshot_hash',
        'template_document_hash', 'fill_policy_hash', 'edits_hash', 'series_id', 'report_role',
        'meeting_key', 'period_key', 'continuity_hash',
    }
    assert set(intent['file_hashes']) == set(names)
    assert set(intent['file_sizes']) == set(names)
    assert set(manifest['file_hashes']) == set(names) - {'manifest.json'}
    assert manifest['schema_version'] == 2
    assert manifest['authoring_schema'] == 'report-authoring/2'
    assert manifest['series_id'] is None
    assert manifest['report_role'] == 'standalone'
    assert manifest['meeting_key'] is None
    assert manifest['period_key'] is None
    assert manifest['continuity_hash'] is None
    assert 'authored_edits' not in revision_two
    assert 'fragment' in revision_two['edits'][0]
    assert 'origin' in revision_two['edits'][0]
    assert 'text' not in revision_two['edits'][0]
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'template.json',
    ) == template_bytes
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'edits.json',
    ) == edits_bytes


def test_should_reject_corrupt_schema2_runtime_packet_before_append_when_hashes_are_repaired(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(505),
        selection=draft_selection(),
        template=builtin_template(),
    )
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(506),
        expected_revision=1,
        expected_revision_hash=draft.revision_hash,
        edits=(authored_note(2, 'Corrupt retained packet guard'),),
    )
    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        service.finalize_and_commit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(507),
            expected_revision=saved.revision,
        )
    before_head = environment.repository.head()
    root = draft_root(environment, draft.draft_id)
    intent_path = root / 'finalization.json'
    intent = decode_json(intent_path.read_bytes())
    packet = root / 'finalization-files' / intent['publication_id']
    edits = decode_json((packet / 'edits.json').read_bytes())
    edits['selected_revision_hash'] = '0' * 64
    edits_bytes = canonical_bytes(edits)
    (packet / 'edits.json').write_bytes(edits_bytes)
    manifest = decode_json((packet / 'manifest.json').read_bytes())
    _replace_packet_hash(manifest, 'edits.json', edits_bytes)
    manifest['edits_hash'] = _hash(edits_bytes)
    manifest_bytes = canonical_bytes(manifest)
    (packet / 'manifest.json').write_bytes(manifest_bytes)
    intent['edits_hash'] = manifest['edits_hash']
    _replace_packet_hash(intent, 'edits.json', edits_bytes)
    _replace_packet_hash(intent, 'manifest.json', manifest_bytes)
    intent['file_sizes']['edits.json'] = len(edits_bytes)
    intent['file_sizes']['manifest.json'] = len(manifest_bytes)
    intent_path.write_bytes(canonical_bytes(intent))

    with pytest.raises(report_api.ReportError) as error:
        service.resume_finalization(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(507),
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert environment.repository.head() == before_head
    assert environment.repository.list_files('report_publications') == ()


def test_should_reject_schema2_manifest_extra_fields_and_mixed_packet(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(510),
        selection=draft_selection(),
        template=builtin_template(),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(511),
        expected_revision=1,
    )
    manifest_path = environment.repository.archive / f'report_publications/{publication.manifest.publication_id}/manifest.json'
    manifest = decode_json(manifest_path.read_bytes())
    manifest['fake_extra_field'] = True
    manifest_path.write_bytes(canonical_bytes(manifest))

    with pytest.raises(report_api.ReportError) as error:
        service.get_publication(environment.actor, environment.project.id, environment.stage.id, publication.manifest.publication_id)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_keep_schema1_legacy_publication_contract_and_literal_text_downloads(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(520),
        selection=draft_selection(),
        template=daily_template(),
    )
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(521),
        expected_revision=1,
        edits=(draft_note(1, '**literal** <script>alert(1)</script>'),),
        template=daily_template(),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(522),
        expected_revision=saved.revision,
    )
    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=saved.revision)
    manifest = decode_json(read_bytes(
        environment.repository.archive,
        f'report_publications/{publication.manifest.publication_id}/manifest.json',
    ))

    assert manifest['schema_version'] == 1
    assert 'manifest.json' not in manifest['file_hashes']
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'html',
    ) == rendered.html_document
    assert b'**literal** &lt;script&gt;alert(1)&lt;/script&gt;' in rendered.html_document
    with pytest.raises(report_api.ReportError):
        service.read_artifact(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            publication.manifest.publication_id,
            'snapshot.json',
        )


def test_should_upgrade_existing_schema1_draft_on_first_authored_save_without_rewriting_old_revision_bytes(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(540),
        selection=draft_selection(),
        template=daily_template(),
    )
    revision_one_path = draft_root(environment, draft.draft_id) / 'revisions' / '00000001.json'
    original_revision_one_bytes = revision_one_path.read_bytes()
    original_revision_one_hash = draft.revision_hash
    literal_wysiwyg_note = report_api.AuthoredEditRequest(
        '60000000-0000-4000-8000-000000000001',
        'note',
        {'scope': 'report'},
        fragment('**literal** <script>alert(1)</script>'),
        None,
    )

    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(541),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(literal_wysiwyg_note,),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(542),
        expected_revision=saved.revision,
    )
    edits = decode_json(service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'edits.json',
    ))
    rendered = service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'html',
    )

    assert revision_one_path.read_bytes() == original_revision_one_bytes
    assert saved.authoring_schema == 'report-authoring/2'
    assert saved.template.version == '2'
    assert canonical_bytes(saved.authored_edits[0].fragment) == canonical_bytes(literal_wysiwyg_note.fragment)
    assert saved.edits[0].text == '**literal** <script>alert(1)</script>'
    assert edits['revisions'][0]['revision_hash'] == original_revision_one_hash
    assert canonical_bytes(edits['revisions'][0]['payload']) == original_revision_one_bytes
    assert edits['revisions'][1]['payload']['schema_version'] == 2
    assert 'fragment' in edits['revisions'][1]['payload']['edits'][0]
    assert b'**literal** &lt;script&gt;alert(1)&lt;/script&gt;' in rendered


def test_should_render_finalize_old_v1_draft_and_upgrade_second_old_draft_with_original_download_intact(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    legacy = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(545),
        selection=replace(draft_selection(), purpose='historical_export'),
        template=daily_template(),
    )
    _pin_schema1_template_hash(environment, legacy.draft_id, draft_command(545), LEGACY_DAILY_TEMPLATE_HASH)
    legacy = service.get(environment.actor, environment.project.id, environment.stage.id, legacy.draft_id)
    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, legacy.draft_id, revision=1)
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        legacy.draft_id,
        command_id=draft_command(546),
        expected_revision=1,
    )
    original_html = service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'html',
    )
    migrating = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(547),
        selection=replace(draft_selection(), purpose='historical_export'),
        template=daily_template(),
    )
    migrating_hash = _pin_schema1_template_hash(environment, migrating.draft_id, draft_command(547), LEGACY_DAILY_TEMPLATE_HASH)

    upgraded = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        migrating.draft_id,
        command_id=draft_command(548),
        expected_revision=1,
        expected_revision_hash=migrating_hash,
        edits=(authored_note(3, 'Authoring upgrade from old v1'),),
    )
    upgraded_publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        migrating.draft_id,
        command_id=draft_command(549),
        expected_revision=upgraded.revision,
    )

    assert legacy.template_definition.template_hash == LEGACY_DAILY_TEMPLATE_HASH
    assert rendered.template_hash == LEGACY_DAILY_TEMPLATE_HASH
    assert upgraded.template.version == '2'
    assert b'Authoring upgrade from old v1' in service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        upgraded_publication.manifest.publication_id,
        'html',
    )
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'html',
    ) == original_html


def test_should_refuse_legacy_save_on_schema2_current_without_losing_original_replay(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(560),
        selection=draft_selection(),
        template=daily_template(),
    )
    legacy_saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(561),
        expected_revision=1,
        edits=(draft_note(2, 'legacy before authored upgrade'),),
        template=daily_template(),
    )
    authored_saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(562),
        expected_revision=legacy_saved.revision,
        expected_revision_hash=legacy_saved.revision_hash,
        edits=(authored_note(4, 'colored authored text'),),
    )

    with pytest.raises(report_api.ReportError) as error:
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(563),
            expected_revision=authored_saved.revision,
            edits=(draft_note(5, 'legacy downgrade attempt'),),
            template=daily_template(),
        )
    replay = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(561),
        expected_revision=1,
        edits=(draft_note(2, 'legacy before authored upgrade'),),
        template=daily_template(),
    )
    current = service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)

    assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'
    assert (replay.revision, replay.revision_hash) == (legacy_saved.revision, legacy_saved.revision_hash)
    assert (current.revision, current.revision_hash) == (authored_saved.revision, authored_saved.revision_hash)
    assert canonical_bytes(current.authored_edits[0].fragment) == canonical_bytes(authored_saved.authored_edits[0].fragment)


def test_should_reject_non_null_preparation_context(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)

    with pytest.raises(report_api.ReportError):
        service.create_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(531),
            selection=draft_selection(),
            template=builtin_template(),
            preparation_id='50000000-0000-4000-8000-000000000002',
        )


def _pin_schema1_template_hash(environment, draft_id, command_id, template_hash):
    root = draft_root(environment, draft_id)
    revision_path = root / 'revisions' / '00000001.json'
    revision = decode_json(revision_path.read_bytes())
    revision['template_definition']['template_hash'] = template_hash
    revision_hash = _hash(canonical_bytes(revision))
    revision_path.write_bytes(canonical_bytes(revision))
    intent_path = root / 'intent.json'
    intent = decode_json(intent_path.read_bytes())
    intent['revision_payload'] = revision
    intent['revision_hash'] = revision_hash
    intent_path.write_bytes(canonical_bytes(intent))
    command_path = root / 'commands' / f'{command_id}.json'
    command = decode_json(command_path.read_bytes())
    command['revision_payload'] = revision
    command['revision_hash'] = revision_hash
    command_path.write_bytes(canonical_bytes(command))
    (root / 'current.json').write_bytes(canonical_bytes({
        'schema_version': 1,
        'revision': 1,
        'revision_hash': revision_hash,
    }))
    return revision_hash


def _replace_packet_hash(value, name, data):
    value['file_hashes'][name] = _hash(data)


def _hash(data):
    return hashlib.sha256(data).hexdigest()
