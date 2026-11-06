from datetime import UTC, datetime
from pathlib import Path

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from project_management.tests.report_completion_fixtures import (
    SyntheticReferenceReader,
    SyntheticSourceReader,
    completion_request,
)
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, draft_command, draft_selection


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
    draft = draft_service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(940),
        selection=draft_selection(),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    return completion, draft


def test_shouldWriteBudgetInStageRuntimeAndNotRetrySameRequest(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    reader = SyntheticReferenceReader()
    completion, draft = build(environment, reader)

    first = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                               completion_request(draft))
    duplicate = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                   completion_request(draft))

    budget_path = environment.repository.runtime / 'report-reference-budget.json'
    wrong_path = environment.config.root / 'projects' / environment.stage.id / 'runtime' / 'report-reference-budget.json'
    assert first.status == 'ready'
    assert duplicate.error.code == 'COMPLETION_REQUEST_REPLAY'
    assert len(reader.calls) == 1
    assert budget_path.exists()
    assert not wrong_path.exists()


def test_shouldFailClosedOnCorruptBudgetWithoutNetwork(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    reader = SyntheticReferenceReader()
    completion, draft = build(environment, reader)
    environment.repository.runtime.mkdir(parents=True, exist_ok=True)
    (environment.repository.runtime / 'report-reference-budget.json').write_bytes(b'{"schema_version":1,"buckets":"bad"}')

    result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                completion_request(draft))

    assert result.error.code == 'COMPLETION_SCOPE_UNAVAILABLE'
    assert reader.calls == []


def test_shouldRejectClockRollbackAndBucketOverflowWithoutTruncation(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    reader = SyntheticReferenceReader()
    completion, draft = build(environment, reader)
    environment.repository.runtime.mkdir(parents=True, exist_ok=True)
    rows = [{'actor_hash': f'{index:064x}', 'admissions': []} for index in range(65)]
    (environment.repository.runtime / 'report-reference-budget.json').write_bytes(canonical_bytes({
        'schema_version': 1,
        'last_observed_at': '2026-11-03T01:01:00+00:00',
        'buckets': rows,
    }))

    result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                completion_request(draft))

    assert result.error.code == 'COMPLETION_SCOPE_UNAVAILABLE'
    assert reader.calls == []


def test_shouldFailClosedOnDuplicateActorBucketsAndNaiveTimes(tmp_path):
    for index, payload in enumerate((
        {
            'schema_version': 1,
            'last_observed_at': '2026-11-03T01:00:00+00:00',
            'buckets': [
                {'actor_hash': 'a' * 64, 'admissions': []},
                {'actor_hash': 'a' * 64, 'admissions': []},
            ],
        },
        {
            'schema_version': 1,
            'last_observed_at': '2026-11-03T01:00:00',
            'buckets': [],
        },
        {
            'schema_version': 1,
            'last_observed_at': '2026-11-03T01:00:00+00:00',
            'buckets': [{
                'actor_hash': 'a' * 64,
                'admissions': [{'request_id': 'AAAAAAAA-AAAA-4AAA-8AAA-000000000001', 'admitted_at': '2026-11-03T01:00:00+00:00'}],
            }],
        },
    ), 950):
        environment = DraftArchive(tmp_path / f'archive-root-{index}')
        reader = SyntheticReferenceReader()
        completion, draft = build(environment, reader)
        environment.repository.runtime.mkdir(parents=True, exist_ok=True)
        (environment.repository.runtime / 'report-reference-budget.json').write_bytes(canonical_bytes(payload))

        result = completion.suggest(environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
                                    completion_request(draft, request_id=f'aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}'))

        assert result.error.code == 'COMPLETION_SCOPE_UNAVAILABLE'
        assert reader.calls == []
