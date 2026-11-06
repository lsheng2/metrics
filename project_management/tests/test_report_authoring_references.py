from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_completion import ReferenceObservation
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_selection,
)


def build_service(environment, verifier):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
        reference_verifier=verifier,
    )


def authored_template():
    return report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {})


def paragraph(*content):
    return {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': list(content)}]}


def text(value, *, marks=(), foreground=None, background=None):
    return {'type': 'text', 'text': value, 'marks': list(marks), 'foreground': foreground, 'background': background}


def link(href, reference_id, *content):
    return {'type': 'link', 'href': href, 'reference_id': reference_id, 'content': list(content)}


def note(value, fragment, receipts=()):
    return report_api.AuthoredEditRequest(
        f'90000000-0000-4000-8000-{value:012d}',
        'note',
        {'scope': 'report'},
        fragment,
        None,
        tuple(receipts),
    )


def observation(identity=None):
    identity = identity or {'provider_id': 'jira', 'endpoint_id': 'alpha-endpoint', 'stable_id': '10001', 'display_key': 'ALPHA-1'}
    if not isinstance(identity, dict):
        identity = {
            'provider_id': identity.provider_id,
            'endpoint_id': identity.endpoint_id,
            'stable_id': identity.stable_id,
            'display_key': 'ALPHA-1',
        }
    return ReferenceObservation(
        identity=identity,
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
    )


def issue(verifier, actor, environment, draft, option='id_title_owner'):
    return verifier.issue_option(
        actor,
        environment.project.id,
        environment.stage.id,
        draft,
        {'scope': 'report'},
        option,
        observation(draft.snapshot.rows[0].identity),
        membership_proof_hash='b' * 64,
        principal_id='principal:archive-owner',
    )


def test_shouldRejectSigningObservationWithMismatchedMembershipProof(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    verifier = ReferenceReceiptVerifier('unit-secret')
    service = build_service(environment, verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(690),
        selection=draft_selection(),
        template=authored_template(),
    )
    bad = replace(observation(draft.snapshot.rows[0].identity), scope_snapshot_hash='a' * 64)

    with pytest.raises(report_api.ReportError) as error:
        verifier.issue_option(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft,
            {'scope': 'report'},
            'id',
            bad,
            membership_proof_hash='b' * 64,
            principal_id='principal:archive-owner',
        )

    assert error.value.code == 'REFERENCE_INVALID'


def test_shouldSaveReferenceReceiptAfterUserEditsTitlePaintAndPublicationKeepsSourceFacts(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    verifier = ReferenceReceiptVerifier('unit-secret')
    service = build_service(environment, verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(700),
        selection=draft_selection(),
        template=authored_template(),
    )
    option = issue(verifier, environment.actor, environment, draft)
    edited = paragraph(
        text('see ', foreground='#0055aa', background=None),
        link(option.fragment['blocks'][0]['content'][0]['href'], option.reference_id,
             text('ALPHA-1', marks=('strong',), foreground='#0055aa', background='#fff4cc')),
        text(' user edited title @Alicia', foreground='#0055aa', background=None),
    )

    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(701),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(note(1, edited, (option.receipt,)),),
    )
    reopened = service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=saved.revision)
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(702),
        expected_revision=saved.revision,
    )
    final_rendered = service.render(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        revision=saved.revision,
    )

    stored = reopened.authored_edits[0].reference_observations[0]
    assert stored['reference_id'] == option.reference_id
    assert stored['content_basis'] == 'human_composed'
    assert stored['observation']['title'] == 'Provider title'
    assert 'user edited title @Alicia' in rendered.html_fragment
    assert f'data-reference-id="{option.reference_id}"' in rendered.html_fragment
    assert reopened.snapshot.rows[0].title == draft.snapshot.rows[0].title
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'report.html',
    ) == final_rendered.html_document


def test_shouldRejectChangedReferenceKeyHrefDuplicateUnknownAndExpiredReceipts(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    verifier = ReferenceReceiptVerifier('unit-secret')
    service = build_service(environment, verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(710),
        selection=draft_selection(),
        template=authored_template(),
    )
    option = issue(verifier, environment.actor, environment, draft, option='id')
    good_link = link(option.fragment['blocks'][0]['content'][0]['href'], option.reference_id, text('ALPHA-1'))

    cases = [
        ('REFERENCE_CONTENT_CHANGED', paragraph(link(good_link['href'], option.reference_id, text('ALPHA-2'))), (option.receipt,)),
        ('REFERENCE_CONTENT_CHANGED', paragraph(link('https://tracker.example.test/jira/browse/ALPHA-2', option.reference_id, text('ALPHA-1'))), (option.receipt,)),
        ('REFERENCE_INVALID', paragraph(
            link(good_link['href'], option.reference_id, text('ALPHA-1')),
            link(good_link['href'], option.reference_id, text('ALPHA-1')),
        ), (option.receipt,)),
        ('REFERENCE_INVALID', paragraph(link(good_link['href'], '11111111-1111-4111-8111-111111111111', text('ALPHA-1'))), ()),
    ]
    for index, (code, fragment, receipts) in enumerate(cases, 711):
        with pytest.raises(report_api.ReportError) as error:
            service.save_authored(
                environment.actor,
                environment.project.id,
                environment.stage.id,
                draft.draft_id,
                command_id=draft_command(index),
                expected_revision=draft.revision,
                expected_revision_hash=draft.revision_hash,
                edits=(note(index, fragment, receipts),),
            )
        assert error.value.code == code

    past = ReferenceReceiptVerifier('unit-secret', clock=lambda: datetime.now(UTC) - timedelta(seconds=301))
    expired = issue(past, environment.actor, environment, draft, option='id')
    with pytest.raises(report_api.ReportError) as error:
        service.save_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(720),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(note(720, paragraph(link(good_link['href'], expired.reference_id, text('ALPHA-1'))), (expired.receipt,)),),
        )
    assert error.value.code == 'REFERENCE_RECEIPT_EXPIRED'


def test_shouldReuseCurrentReferenceObservationButNotResurrectDeletedLinks(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    verifier = ReferenceReceiptVerifier('unit-secret')
    service = build_service(environment, verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(730),
        selection=draft_selection(),
        template=authored_template(),
    )
    option = issue(verifier, environment.actor, environment, draft, option='id')
    original = paragraph(link(option.fragment['blocks'][0]['content'][0]['href'], option.reference_id, text('ALPHA-1')))
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(731),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(note(731, original, (option.receipt,)),),
    )

    reused = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(732),
        expected_revision=saved.revision,
        expected_revision_hash=saved.revision_hash,
        edits=(note(731, paragraph(text('prefix '), original['blocks'][0]['content'][0], text(' suffix')), ()),),
    )
    deleted = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(733),
        expected_revision=reused.revision,
        expected_revision_hash=reused.revision_hash,
        edits=(note(731, paragraph(text('ALPHA-1 as ordinary text')), (option.receipt,)),),
    )

    assert len(reused.authored_edits[0].reference_observations) == 1
    assert deleted.authored_edits[0].reference_observations == ()


def test_shouldRejectForgedPersistedReferenceObservationOnReuse(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    verifier = ReferenceReceiptVerifier('unit-secret')
    service = build_service(environment, verifier)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(734),
        selection=draft_selection(),
        template=authored_template(),
    )
    ref_id = '11111111-1111-4111-8111-111111111111'
    forged = {
        'reference_id': ref_id,
        'option_id': 'id',
        'issued_fragment_hash': 'c' * 64,
        'content_basis': 'human_composed',
        'observation': {
            **asdict(observation()),
            'scope_snapshot_hash': 'd' * 64,
        },
    }
    old = SimpleNamespace(edit_id='old', target={'scope': 'report'}, reference_observations=(forged,))
    request = note(735, paragraph(link('https://tracker.example.test/jira/browse/ALPHA-1', ref_id, text('ALPHA-1'))))
    membership = service.source_reader.membership(environment.actor, environment.project.id, environment.stage.id, draft.snapshot)

    with pytest.raises(report_api.ReportError) as error:
        verifier.verify_requests(
            environment.actor.subject,
            environment.project.id,
            environment.stage.id,
            draft,
            (request,),
            (old,),
            membership,
        )

    assert error.value.code == 'REFERENCE_INVALID'
