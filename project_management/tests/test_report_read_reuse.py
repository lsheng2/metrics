from uuid import uuid4

import pytest

from project_management.app.api import reports as report_api
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command


def test_operation_events_read_immutable_request_once_per_observation(tmp_path, monkeypatch):
    from project_management.storage.project_operations import ProjectOperationRepository

    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    first = environment.run_service.submit(
        environment.actor, environment.project.id, environment.stage.id, environment.request(str(uuid4())),
    )
    original = ProjectOperationRepository._required_request
    calls = []

    def counted(store, operation_id):
        calls.append(operation_id)
        return original(store, operation_id)

    monkeypatch.setattr(ProjectOperationRepository, '_required_request', counted)
    observed = environment.run_service.get(
        environment.actor, environment.project.id, environment.stage.id, first.operation_id,
    )
    assert observed == first
    assert calls == [first.operation_id]


def test_revision_hash_chain_scans_commands_once(tmp_path, monkeypatch):
    import project_management.storage.report_drafts as module
    from project_management.tests.report_draft_fixtures import draft_note
    from project_management.tests.report_render_fixtures import daily_template

    environment = DraftArchive(tmp_path / 'archive-root')
    service = report_api.ReportDraftService(
        environment, StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(), clock=FixedClock(),
    )
    draft = service.create(
        environment.actor, environment.project.id, environment.stage.id, command_id=draft_command(17300),
        selection=report_api.ReportSelection(capture_id=draft_command(17301)), template=daily_template(),
    )
    for index in range(4):
        draft = service.save(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(17302 + index), expected_revision=draft.revision,
            edits=(draft_note(50 + index),), template=daily_template(),
        )
    original = module.read_bytes
    counts = {}

    def measured(root, path, **kwargs):
        if str(path).startswith('commands/'):
            counts[str(path)] = counts.get(str(path), 0) + 1
        return original(root, path, **kwargs)

    monkeypatch.setattr(module, 'read_bytes', measured)
    result = service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    assert result.revision == 5
    assert max(counts.values()) == 1, counts


def test_canonical_scalar_fast_path_preserves_exact_bytes(monkeypatch):
    from project_management.app.domain import capture_values

    original = capture_values.is_dataclass
    inspections = []

    def inspected(value):
        inspections.append(type(value))
        return original(value)

    monkeypatch.setattr(capture_values, 'is_dataclass', inspected)
    assert capture_values.canonical_bytes({'a': [None, True, 12, 1.5, 'word']}) == b'{"a":[null,true,12,1.5,"word"]}'
    assert not any(kind in (str, bool, int, float, type(None)) for kind in inspections)


def test_same_revision_in_intent_command_and_file_is_decoded_once(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from project_management.app.domain.capture_values import canonical_bytes
    from project_management.app.domain import report_draft_values
    from project_management.storage import report_drafts
    from project_management.storage.archive_read_view import GitArchiveReadView
    from project_management.storage.git import GitResult
    from project_management.tests.report_render_fixtures import daily_template

    environment = DraftArchive(tmp_path / 'archive-root')
    service = report_api.ReportDraftService(
        environment, StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(), clock=FixedClock(),
    )
    draft = service.create(
        environment.actor, environment.project.id, environment.stage.id, command_id=draft_command(17400),
        selection=report_api.ReportSelection(capture_id=draft_command(17401)), template=daily_template(),
    )
    repository = environment.repository
    repository.config = environment.config
    repository.git = SimpleNamespace(run=lambda *args, **kwargs: GitResult(
        0, b'\0R\0' + repository.head().encode() + b'\0\0' + b'b' * 40 + b'\0',
    ))
    original = report_draft_values.revision_from_mapping
    decoded = []

    def counted(value):
        decoded.append(canonical_bytes(value))
        return original(value)

    monkeypatch.setattr(report_draft_values, 'revision_from_mapping', counted)
    monkeypatch.setattr(report_drafts, 'revision_from_mapping', counted)
    with GitArchiveReadView(repository) as view:
        result = report_drafts.ReportDraftStore(view, environment.root, environment.config.limits, service.limits).read_draft(draft.draft_id)
    assert result == draft
    assert len(decoded) == 1


def test_operation_listing_overlaps_reads_but_preserves_order(tmp_path, monkeypatch):
    from threading import Barrier
    from project_management.storage.project_operations import ProjectOperationRepository

    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    expected = []
    for _ in range(3):
        operation = environment.run_service.submit(
            environment.actor, environment.project.id, environment.stage.id, environment.request(str(uuid4())),
        )
        expected.append(environment.run_service.cancel(
            environment.actor, environment.project.id, environment.stage.id,
            operation.operation_id, expected_revision=operation.revision,
        ))
    original = ProjectOperationRepository.current
    barrier = Barrier(3, timeout=2)

    def parallel_current(store, operation_id):
        barrier.wait()
        return original(store, operation_id)

    monkeypatch.setattr(ProjectOperationRepository, 'current', parallel_current)
    result = environment.run_service.list(environment.actor, environment.project.id, environment.stage.id)
    assert result == tuple(sorted(expected, key=lambda row: (row.created_at, row.operation_id), reverse=True))
