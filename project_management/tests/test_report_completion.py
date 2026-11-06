from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.contracts import ScopeDescriptor
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.app.api.references import ADAPTER_REVISION, JiraProviderReferenceReader
from provider_sync.tests.capture_gateway_fixtures import JiraFixture
from project_management.tests.report_completion_fixtures import (
    SyntheticReferenceReader,
    SyntheticSourceReader,
    completion_request,
)
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily,
    history_fixture,
    prepare_daily,
    ref_for,
    weekly_document,
)
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    draft_command,
    draft_selection,
)


def build(environment, reader):
    source = SyntheticSourceReader(source_commit=environment.repository.head(),
                                   rule_hash=environment.stage.definition_hash)
    draft_service = report_api.ReportDraftService(
        environment,
        source,
        report_api.ReportRenderer(),
        clock=FixedClock(),
        reference_verifier=ReferenceReceiptVerifier('unit-secret'),
    )
    completion = ReportCompletionService(
        draft_service,
        source,
        reader,
        ReferenceReceiptVerifier('unit-secret'),
        CompletionAdmissionStore(environment.config.root),
        clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
    )
    return draft_service, completion


def create_draft(service, environment):
    return service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(740),
        selection=draft_selection(),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )


def test_shouldReturnThreeSignedOptionsAndDisableOwnerWhenUnassigned(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    reader = SyntheticReferenceReader()
    draft_service, completion = build(environment, reader)
    draft = create_draft(draft_service, environment)

    result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, completion_request(draft))

    assert result.status == 'ready', result.error
    assert [option.option_id for option in result.options] == ['id', 'id_title', 'id_title_owner']
    assert [option.enabled for option in result.options] == [True, True, False]
    assert result.options[0].fragment['blocks'][0]['content'][0]['reference_id'] != result.options[1].fragment['blocks'][0]['content'][0]['reference_id']
    assert result.options[2].disabled_reason == 'unassigned'
    assert len(reader.calls) == 1


def test_shouldUseQualifiedJiraReaderThroughCompletionServiceWithSyntheticTransport(tmp_path):
    class JiraSourceReader(SyntheticSourceReader):
        def membership(self, actor, project_id, stage_id, snapshot):
            from project_management.services.report_membership import ScopeMember, ScopeMembershipSnapshot
            from project_management.app.api.capture_archive import WorkItemIdentity

            identity = WorkItemIdentity('jira', 'alpha-endpoint', '101', 'ALPHA-101')
            source_key = replace(snapshot.rows[0].source_key, stable_id='101')
            return ScopeMembershipSnapshot(
                1, snapshot.capture_id, snapshot.source_commit, 'a' * 64, snapshot.source_as_of,
                snapshot.rule_hash, 'principal-1', 'complete', 1, 1,
                (ScopeMember(identity, source_key),), 'b' * 64,
            )

    environment = DraftArchive(tmp_path / 'archive-root-qualified')
    source = JiraSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    verifier = ReferenceReceiptVerifier('unit-secret')
    draft_service = report_api.ReportDraftService(
        environment,
        source,
        report_api.ReportRenderer(),
        clock=FixedClock(),
        reference_verifier=verifier,
    )
    fixture = JiraFixture(environment)
    info = fixture.resolver.describe_profile(environment.stage.descriptor.profile_id, expected_provider_id='jira')
    reader = JiraProviderReferenceReader(
        fixture.resolver,
        ({
            'profile_id': environment.stage.descriptor.profile_id,
            'provider_id': 'jira',
            'endpoint_id': info.endpoint.endpoint_id,
            'auth_mode': info.endpoint.auth_mode,
            'principal_id': 'principal-1',
            'adapter_revision': ADAPTER_REVISION,
            'qualification_ref': 'approved-reference-reader',
        },),
        reader_factory=fixture.reader_factory,
        clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
    )
    completion = ReportCompletionService(
        draft_service,
        source,
        reader,
        verifier,
        CompletionAdmissionStore(environment.config.root),
        clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
    )
    draft = create_draft(draft_service, environment)

    result = completion.suggest(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        completion_request(draft, '#ALPHA-101'),
    )

    assert result.status == 'ready', result.error
    assert result.options[1].enabled
    assert [path for _, path, _ in fixture.transport.requests] == [
        '/jira/rest/api/2/myself',
        '/jira/rest/api/2/issue/101',
    ]


def test_shouldFailScopeAndQualificationBeforeProviderOrBudget(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    reader = SyntheticReferenceReader(qualified=False)
    draft_service, completion = build(environment, reader)
    draft = create_draft(draft_service, environment)

    outside = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                 completion_request(draft, '#BETA-9'))
    unqualified = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                     completion_request(draft, '#ALPHA-1', 'aaaaaaaa-aaaa-4aaa-8aaa-000000000002'))

    assert outside.error.code == 'COMPLETION_OUTSIDE_REPORT_SCOPE'
    assert unqualified.error.code == 'COMPLETION_PROVIDER_UNQUALIFIED'
    assert reader.calls == []


def test_shouldUseStageProviderNoFallbackAndShareRollingAdmission(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    hsd_descriptor = ScopeDescriptor('hsdes', 'alpha-hsd', 'https://hsd.example.test', 'query:1', 'saved_query', '150', 'v1')
    hsd_stage = replace(environment.stage, descriptor=hsd_descriptor, definition_hash=hsd_descriptor.definition_hash())
    environment.stage = hsd_stage
    environment.repository.stage = hsd_stage
    reader = SyntheticReferenceReader()
    draft_service, completion = build(environment, reader)
    draft = create_draft(draft_service, environment)

    mismatch = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                  completion_request(draft, '#ALPHA-1'))
    assert mismatch.error.code == 'COMPLETION_PROVIDER_MISMATCH'
    assert reader.calls == []

    environment.stage = replace(environment.stage, descriptor=replace(hsd_descriptor, provider_id='jira'),
                                definition_hash=environment.stage.definition_hash)
    environment.repository.stage = environment.stage
    for index in range(30):
        completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                           completion_request(draft, '#ALPHA-1', f'aaaaaaaa-aaaa-4aaa-8aaa-{index + 10:012d}'))
    limited = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                 completion_request(draft, '#ALPHA-1', 'aaaaaaaa-aaaa-4aaa-8aaa-000000000999'))

    assert limited.error.code == 'COMPLETION_RATE_LIMITED'
    assert limited.error.retry_after_seconds > 0
    assert len(reader.calls) == 30


def test_shouldRejectFinalizedDraftBeforeProviderRead(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root-finalized')
    reader = SyntheticReferenceReader()
    draft_service, completion = build(environment, reader)
    draft = create_draft(draft_service, environment)
    draft_service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(799),
        expected_revision=draft.revision,
    )

    result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                completion_request(draft))

    assert result.error.code == 'REPORT_FINALIZED'
    assert reader.calls == []


@pytest.mark.django_db(transaction=True)
def test_shouldAuthorizeCurrentContinuityNoteButRejectHistoricalNoteBeforeProvider(tmp_path):
    fixture = history_fixture(tmp_path)
    reader = SyntheticReferenceReader()
    completion = ReportCompletionService(
        fixture.draft_service,
        fixture.source_reader,
        reader,
        ReferenceReceiptVerifier('unit-secret'),
        CompletionAdmissionStore(fixture.archive.config.root),
        clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
    )
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 note.', '#0055aa', draft_command(8610))
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id,
        saved1.draft_id, command_id=draft_command(8611), expected_revision=saved1.revision,
    )
    fixture.source_reader.source_commit = publication1.commit_id
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication1))
    draft2 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day2.command_id, selection=day2.selection,
        template=fixture.template_selection, preparation_id=day2.preparation_id,
    )
    current_note = draft2.authoring_context['current_observations'][0]['note_id']
    historical_note = saved1.authoring_context['current_observations'][0]['note_id']
    token = '#' + draft2.snapshot.rows[0].identity.display_key

    current = completion.suggest(
        fixture.actor, fixture.project.id, fixture.stage.id, draft2.draft_id,
        replace(completion_request(draft2, token=token), region_target={'scope': 'daily_note', 'note_id': current_note}),
    )
    historical = completion.suggest(
        fixture.actor, fixture.project.id, fixture.stage.id, draft2.draft_id,
        replace(completion_request(draft2, token=token, request_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000222'),
                region_target={'scope': 'daily_note', 'note_id': historical_note}),
    )

    assert current.status == 'ready', current.error
    assert historical.error.code == 'REPORT_EDIT_TARGET_INVALID'
    assert len(reader.calls) == 1


@pytest.mark.django_db(transaction=True)
def test_shouldRejectWeeklyViewCompletionBeforeProvider(tmp_path):
    fixture = history_fixture(tmp_path)
    reader = SyntheticReferenceReader()
    completion = ReportCompletionService(
        fixture.draft_service,
        fixture.source_reader,
        reader,
        ReferenceReceiptVerifier('unit-secret'),
        CompletionAdmissionStore(fixture.archive.config.root),
        clock=lambda: datetime(2026, 11, 3, 1, 0, tzinfo=UTC),
    )
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    saved1 = create_saved_daily(fixture, day1, 1, 'Day1 note.', '#0055aa', draft_command(8620))
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id,
        saved1.draft_id, command_id=draft_command(8621), expected_revision=saved1.revision,
    )
    weekly = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8622), name='Weekly matrix',
        document=weekly_document(), fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    draft = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8623), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45', selected_publication_refs=(ref_for(publication1),),
        template=report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash),
    )
    note_id = draft.authoring_context['current_observations'][0]['note_id']

    result = completion.suggest(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        replace(completion_request(draft), region_target={'scope': 'daily_note', 'note_id': note_id}),
    )

    assert result.error.code == 'REPORT_EDIT_TARGET_INVALID'
    assert reader.calls == []


def test_shouldRecheckLifecycleAfterProviderReadBeforeIssuingOptions(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root-finalized-after')
    reader = SyntheticReferenceReader()
    draft_service, completion = build(environment, reader)
    draft = create_draft(draft_service, environment)

    def finalize_after_read():
        draft_service.finalize_and_commit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(798),
            expected_revision=draft.revision,
        )

    reader.after_read = finalize_after_read
    result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                completion_request(draft))

    assert result.error.code == 'REPORT_FINALIZED'


def test_shouldMapProviderErrorsPreciselyWithDefaultRetryAfter(tmp_path):
    cases = [
        (AccessError('PROVIDER_RATE_LIMITED', provider_status=429), 'COMPLETION_RATE_LIMITED', 60),
        (AccessError('PROVIDER_RESPONSE_INVALID', provider_status=200), 'COMPLETION_RESPONSE_INVALID', None),
        (AccessError('CAPTURE_DEADLINE_EXPIRED'), 'COMPLETION_TIMEOUT', None),
        (AccessError('CAPTURE_RESPONSE_LIMIT'), 'COMPLETION_RESPONSE_INVALID', None),
        (AccessError('PRINCIPAL_CHANGED'), 'COMPLETION_PRINCIPAL_CHANGED', None),
    ]
    for index, (provider_error, code, retry_after) in enumerate(cases, 800):
        environment = DraftArchive(tmp_path / f'archive-root-{index}')
        reader = SyntheticReferenceReader(error=provider_error)
        draft_service, completion = build(environment, reader)
        draft = create_draft(draft_service, environment)

        result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                    completion_request(draft, request_id=f'aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}'))

        assert result.error.code == code
        assert result.error.retry_after_seconds == retry_after
