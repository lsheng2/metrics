import hashlib
from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.report_completion import ReferenceObservation
from project_management.models import Project
from project_management.models_report_templates import ReportTemplateUse
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.storage.paths import read_bytes
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_root,
    draft_selection,
)
from project_management.tests.report_render_fixtures import safe_snapshot


def text_fragment(value):
    if value == '':
        return {'schema_version': 2, 'blocks': []}
    return {
        'schema_version': 2,
        'blocks': [{
            'type': 'paragraph',
            'content': [{
                'type': 'text',
                'text': value,
                'marks': [],
                'foreground': None,
                'background': None,
            }],
        }],
    }


def data_block(source, index):
    return {
        'kind': 'data',
        'block_id': f'81000000-0000-4000-8000-{index:012d}',
        'source': source,
        'options': {'group_by': 'none', 'sort_by': 'key', 'optional_columns': ['source_hash']},
    }


def slot_block(slot_id, *, required=True):
    return {
        'kind': 'slot',
        'block_id': '82000000-0000-4000-8000-000000000001',
        'slot_id': slot_id,
        'label': 'Manual status note',
        'required': required,
        'initial': text_fragment(''),
        'fill_mode': 'manual',
    }


def pinned_document(slot_id):
    return {
        'schema_version': 1,
        'report_kind': 'daily',
        'blocks': [
            {
                'kind': 'content',
                'block_id': '83000000-0000-4000-8000-000000000001',
                'fragment': text_fragment('Pinned literal {{danger}} {% if source %}'),
            },
            data_block('register', 1),
            slot_block(slot_id),
            data_block('coverage', 2),
            data_block('key_messages', 3),
            data_block('changes', 4),
        ],
    }


def weekly_pinned_document(slot_id):
    return {
        'schema_version': 1,
        'report_kind': 'weekly',
        'blocks': [
            {
                'kind': 'content',
                'block_id': '86000000-0000-4000-8000-000000000001',
                'fragment': text_fragment('Weekly intro'),
            },
            data_block('weekly_timeline', 5),
            data_block('coverage', 2),
            data_block('register', 1),
            data_block('key_messages', 3),
            data_block('changes', 4),
            slot_block(slot_id, required=False),
        ],
    }


def ready_template(actor, project_id, *, command, slot_id='84000000-0000-4000-8000-000000000001',
                   document=None, name='Pinned daily'):
    return report_api.ReportTemplateService(clock=FixedClock()).create(
        actor,
        project_id,
        command_id=command,
        name=name,
        document=document or pinned_document(slot_id),
        fill_policy={'schema_version': 1, 'instructions': {}},
    )


def slot_fill(value, slot_id='84000000-0000-4000-8000-000000000001', *, receipts=(), edit=1):
    return report_api.AuthoredEditRequest(
        f'85000000-0000-4000-8000-{edit:012d}',
        'slot_fill',
        {'scope': 'template_slot', 'slot_id': slot_id},
        text_fragment(value),
        None,
        tuple(receipts),
    )


def register_project(environment):
    Project.objects.create(
        id=environment.project.id,
        owner_subject=environment.actor.subject,
        key=environment.project.key,
        name=environment.project.name,
        archived=environment.project.archived,
    )


def build_service(environment, *, source=None, verifier=None):
    source = source or StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    return report_api.ReportDraftService(
        environment,
        source,
        report_api.ReportRenderer(),
        clock=FixedClock(),
        reference_verifier=verifier,
    )


def weekly_source_snapshot():
    snapshot = safe_snapshot()
    return replace(
        snapshot,
        days=(replace(snapshot.days[0], publication_id='87000000-0000-4000-8000-000000000001'), snapshot.days[1]),
    )


@pytest.mark.django_db(transaction=True)
def test_user_template_slot_fill_render_finalize_and_fresh_download_stays_pinned(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    register_project(environment)
    template_service = report_api.ReportTemplateService(clock=FixedClock())
    template = ready_template(environment.actor, environment.project.id, command=draft_command(2000))
    draft_service = build_service(environment)
    selection = report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash)

    draft = draft_service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(2001),
        selection=draft_selection(),
        template=selection,
    )
    template_service.save(
        environment.actor,
        environment.project.id,
        str(template.template_id),
        command_id=draft_command(2002),
        expected_revision=template.revision,
        expected_revision_hash=template.revision_hash,
        name='Pinned daily v2',
        document={**pinned_document('84000000-0000-4000-8000-000000000001'), 'blocks': [
            {**pinned_document('84000000-0000-4000-8000-000000000001')['blocks'][0],
             'fragment': text_fragment('V2 must not render')},
            *pinned_document('84000000-0000-4000-8000-000000000001')['blocks'][1:],
        ]},
        fill_policy={'schema_version': 1, 'instructions': {}},
    )
    empty_saved = draft_service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2003),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill('', edit=2),),
    )
    reopened = build_service(environment).get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    draft_render = build_service(environment).render(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        revision=empty_saved.revision,
    )

    with pytest.raises(report_api.ReportError) as required:
        build_service(environment).finalize_and_commit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(2004),
            expected_revision=empty_saved.revision,
        )
    assert not (draft_root(environment, draft.draft_id) / 'finalization.json').exists()

    filled = build_service(environment).save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2005),
        expected_revision=empty_saved.revision,
        expected_revision_hash=empty_saved.revision_hash,
        edits=(slot_fill('Manual answer {{danger}} {% for row in rows %}', edit=3),),
    )
    publication = build_service(environment).finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2006),
        expected_revision=filled.revision,
    )
    fresh = build_service(environment)
    publication_root = f'report_publications/{publication.manifest.publication_id}'
    files = tuple(sorted(path.split('/')[-1] for path in environment.repository.list_files(publication_root)))
    template_json = decode_json(fresh.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'template.json',
    ))
    edits_json = decode_json(fresh.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'edits.json',
    ))
    html = fresh.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'html',
    )

    assert reopened.authored_edits[0].kind == 'slot_fill'
    assert draft_render.revision == empty_saved.revision
    assert required.value.code == 'REPORT_REQUIRED_SLOT_EMPTY'
    assert ReportTemplateUse.objects.count() == 1
    assert files == ('edits.json', 'manifest.json', 'report.html', 'report.txt', 'snapshot.json', 'template.json')
    assert fresh.get_publication(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
    ).manifest.template_hash == template.presentation_hash
    assert template_json['presentation_hash'] == template.presentation_hash
    assert template_json['resolved_document']['blocks'][0]['fragment']['blocks'][0]['content'][0]['text'].startswith('Pinned literal')
    assert edits_json['revisions'][-1]['payload']['edits'][0]['kind'] == 'slot_fill'
    assert b'Pinned literal {{danger}} {% if source %}' in html
    assert b'Manual answer {{danger}} {% for row in rows %}' in html
    assert b'V2 must not render' not in html


@pytest.mark.django_db(transaction=True)
def test_slot_fill_requires_real_reference_receipts_and_reuses_verified_observation(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    register_project(environment)
    verifier = ReferenceReceiptVerifier('unit-secret')
    template = ready_template(environment.actor, environment.project.id, command=draft_command(2010))
    service = build_service(environment, verifier=verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(2011),
        selection=draft_selection(),
        template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
    )
    target = {'scope': 'template_slot', 'slot_id': '84000000-0000-4000-8000-000000000001'}
    option = verifier.issue_option(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft,
        target,
        'id',
        ReferenceObservation(
            identity=draft.snapshot.rows[0].identity,
            requested_key='ALPHA-1',
            current_key='ALPHA-1',
            canonical_url='https://tracker.example.test/jira/browse/ALPHA-1',
            title='Provider title',
            assignee={'id': 'dev-a', 'display_name': 'Alice'},
            assignee_state='assigned',
            observed_at='2026-11-03T01:00:00+00:00',
            source_updated_at='2026-11-02T23:59:00+00:00',
            lookup_kind='live',
            scope_snapshot_hash='b' * 64,
        ),
        membership_proof_hash='b' * 64,
        principal_id='principal:archive-owner',
    )

    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2012),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '85000000-0000-4000-8000-000000000010',
            'slot_fill',
            target,
            option.fragment,
            None,
            (option.receipt,),
        ),),
    )
    with pytest.raises(report_api.ReportError) as forged:
        service.save_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(2013),
            expected_revision=saved.revision,
            expected_revision_hash=saved.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '85000000-0000-4000-8000-000000000011',
                'slot_fill',
                target,
                {
                    'schema_version': 2,
                    'blocks': [{
                        'type': 'paragraph',
                        'content': [{
                            'type': 'link',
                            'href': 'https://tracker.example.test/jira/browse/ALPHA-1',
                            'reference_id': '11111111-1111-4111-8111-111111111111',
                            'content': [{
                                'type': 'text',
                                'text': 'ALPHA-1',
                                'marks': [],
                                'foreground': None,
                                'background': None,
                            }],
                        }],
                    }],
                },
                None,
                (),
            ),),
        )

    assert saved.authored_edits[0].reference_observations[0]['reference_id'] == option.reference_id
    assert forged.value.code == 'REFERENCE_INVALID'


@pytest.mark.django_db(transaction=True)
def test_published_user_template_snapshot_semantics_are_revalidated_by_readers(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    register_project(environment)
    template = ready_template(environment.actor, environment.project.id, command=draft_command(2020))
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(2021),
        selection=draft_selection(),
        template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
    )
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2022),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill('Ready for publication', edit=20),),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2023),
        expected_revision=saved.revision,
    )
    root = f'report_publications/{publication.manifest.publication_id}'
    template_path = environment.repository.archive / root / 'template.json'
    manifest_path = environment.repository.archive / root / 'manifest.json'
    template_payload = decode_json(template_path.read_bytes())
    template_payload['presentation_hash'] = '0' * 64
    template_bytes = canonical_bytes(template_payload)
    template_path.write_bytes(template_bytes)
    manifest = decode_json(manifest_path.read_bytes())
    manifest['template_hash'] = '0' * 64
    manifest['template_snapshot_hash'] = _hash(template_bytes)
    manifest['file_hashes']['template.json'] = _hash(template_bytes)
    manifest_path.write_bytes(canonical_bytes(manifest))

    with pytest.raises(report_api.ReportError) as error:
        service.get_publication(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            publication.manifest.publication_id,
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.django_db(transaction=True)
def test_weekly_pinned_template_renders_timeline_days_in_document_order_without_plain_text_headers(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    register_project(environment)
    slot_id = '84000000-0000-4000-8000-000000000001'
    template = ready_template(
        environment.actor,
        environment.project.id,
        command=draft_command(2030),
        slot_id=slot_id,
        document=weekly_pinned_document(slot_id),
        name='Pinned weekly',
    )
    service = build_service(environment, source=StaticSourceReader(
        snapshot=weekly_source_snapshot(),
        source_commit=environment.repository.head(),
        rule_hash=environment.stage.definition_hash,
    ))
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(2031),
        selection=draft_selection(),
        template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
    )
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2032),
        expected_revision=draft.revision,
    )
    plain = service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'plain_text',
    ).decode('utf-8')

    assert draft.template.template_id == str(template.template_id)
    assert '2026-11-01: Published publication 87000000-0000-4000-8000-000000000001' in plain
    assert '2026-11-02: No published report publication None' in plain
    assert 'No published report; coverage membership.state=no_publication' in plain
    assert plain.count('Project: Demo Project / Silicon Bring-up') == 1
    assert plain.count('Template hash:') == 1
    assert plain.index('Weekly intro') < plain.index('Weekly timeline\n2026-11-01')
    assert plain.index('Weekly timeline\n2026-11-01') < plain.index('Evidence and coverage')
    assert plain.index('Evidence and coverage') < plain.index('Issue register')
    assert plain.index('Issue register') < plain.index('Key messages')
    assert plain.index('Key messages') < plain.index('Changes')


@pytest.mark.django_db(transaction=True)
def test_readonly_get_rejects_fully_rehashed_saved_revision_with_mismatched_pinned_snapshot(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    register_project(environment)
    template = ready_template(environment.actor, environment.project.id, command=draft_command(2040))
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(2041),
        selection=draft_selection(),
        template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
    )
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(2042),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill('Ready', edit=42),),
    )
    root = draft_root(environment, draft.draft_id)
    revision_path = root / 'revisions' / '00000002.json'
    revision = decode_json(revision_path.read_bytes())
    changed_document = pinned_document('84000000-0000-4000-8000-000000000001')
    changed_document['blocks'][0]['fragment'] = text_fragment('Corrupt but internally valid')
    revision['template_snapshot']['resolved_document'] = changed_document
    revision['template_snapshot']['presentation_hash'] = report_api.template_document_presentation_hash(changed_document)
    revision_bytes = canonical_bytes(revision)
    revision_hash = _hash(revision_bytes)
    revision_path.write_bytes(revision_bytes)
    command_path = root / 'commands' / f'{draft_command(2042)}.json'
    command = decode_json(command_path.read_bytes())
    command['revision_payload'] = revision
    command['revision_hash'] = revision_hash
    command_path.write_bytes(canonical_bytes(command))
    (root / 'current.json').write_bytes(canonical_bytes({
        'schema_version': 1,
        'revision': saved.revision,
        'revision_hash': revision_hash,
    }))

    with pytest.raises(report_api.ReportError) as error:
        build_service(environment).get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def _hash(data):
    return hashlib.sha256(data).hexdigest()
