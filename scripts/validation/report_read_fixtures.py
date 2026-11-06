from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.captures import (
    CaptureCoverage,
    CaptureIntent,
    CaptureSourceIdentity,
    MembershipInput,
    PartCoverage,
    RawPageInput,
    SnapshotInput,
    WorkItemIdentity,
)
from project_management.app.domain.report_contracts import ReportSelection
from project_management.app.domain.report_publication_contracts import ReportPublicationArtifacts
from project_management.services.report_queries import ReportQueryService
from scripts.validation.report_read_git import PublicationBuffer, buffered_report_repository, fast_import_records
from scripts.validation.report_read_scale import materialize_scale_captures
from project_management.tests.history_persistence_fixtures import (
    create_saved_daily,
    git_head,
    history_fixture,
    prepare_daily,
    ref_for,
)
from project_management.tests.report_draft_fixtures import draft_command


@dataclass(frozen=True, slots=True)
class ReportReadFixture:
    actor: object
    project_id: str
    stage_id: str
    query_service: ReportQueryService
    source_commit: str
    fixture_digest: str
    capture_ids: tuple[str, ...]
    draft_ids: tuple[str, ...]
    publication_ids: tuple[str, ...]
    publication_packets: tuple[ReportPublicationArtifacts, ...] = ()


def create_report_read_fixture(
    tmp_path: Path,
    *,
    captures: int = 2,
    publications: int = 3,
    revisions_per_draft: int = 1,
) -> ReportReadFixture:
    if captures < 1 or publications < 1 or revisions_per_draft < 1:
        raise ValueError('fixture sizes must be positive')
    fixture = history_fixture(tmp_path)
    capture_ids = _create_captures(fixture, captures)
    drafts, publication_ids = [], []
    baseline = None
    for index in range(publications):
        fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
        daily = prepare_daily(fixture, index + 1, _fixture_day(index), baseline)
        if revisions_per_draft == 1:
            draft = fixture.draft_service.create_authored(
                fixture.actor,
                fixture.project.id,
                fixture.stage.id,
                command_id=daily.command_id,
                selection=daily.selection,
                template=fixture.template_selection,
                preparation_id=daily.preparation_id,
            )
        else:
            draft = create_saved_daily(
                fixture,
                daily,
                index + 1,
                f'Synthetic authored daily note {index + 1}.',
                '#334455',
                draft_command(18000 + index * 10 + 1),
            )
            draft = _save_revisions(fixture, draft, index, revisions_per_draft)
        publication = fixture.draft_service.finalize_and_commit(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            draft.draft_id,
            command_id=draft_command(18000 + index * 10 + 9),
            expected_revision=draft.revision,
        )
        baseline = ref_for(publication)
        drafts.append(draft.draft_id)
        publication_ids.append(publication.manifest.publication_id)
    source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    return ReportReadFixture(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        ReportQueryService(fixture.archive, fixture.draft_service),
        source_commit,
        _digest({'captures': capture_ids, 'drafts': drafts, 'publications': publication_ids, 'head': source_commit}),
        tuple(capture_ids),
        tuple(drafts),
        tuple(publication_ids),
    )


def create_standalone_scale_fixture(
    tmp_path: Path,
    *,
    captures: int = 100,
    publications: int = 100,
    revisions_per_draft: int = 5,
    actor_subject: str = 'archive-owner',
    archive_config=None,
    progress=None,
) -> ReportReadFixture:
    if captures < 1 or publications < 1 or revisions_per_draft < 1:
        raise ValueError('fixture sizes must be positive')
    fixture = history_fixture(tmp_path, actor_subject=actor_subject, archive_config=archive_config)
    from project_management.models import ProjectStage

    ProjectStage.objects.filter(id=fixture.stage.id).update(
        descriptor_json=asdict(fixture.stage.descriptor), selection_json=asdict(fixture.stage.selection),
    )
    if progress is not None:
        progress(0)
    capture_ids = materialize_scale_captures(
        fixture,
        captures,
        fixed_items=_fixed_items,
        page_factory=_page,
        snapshot_factory=_snapshot,
        source_hash=_source_hash,
    )
    source_head = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    fixture.source_reader.source_commit = source_head
    from project_management.out.ai_task_contract import AiTaskContract
    from project_management.services.report_sources import ReportSourceReader
    from project_management.tests.summary_fixtures import PACK_ROOT
    from project_management.storage.repository import CaptureArchiveRepository

    fixture.source_reader.snapshot = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT)).read(
        fixture.actor, fixture.project.id, fixture.stage.id, ReportSelection(capture_id=capture_ids[-1]),
    )
    if len(fixture.source_reader.snapshot.rows) != 3:
        raise ValueError('Scale source must contain three real captured rows.')
    buffer = PublicationBuffer(source_head)
    drafts, publication_ids = [], []
    original = fixture.archive._report_repository
    deadline = monotonic() + 300
    # Scale generation tests the readers. Identity and quota checks have separate native producer tests.
    with patch.object(fixture.archive, '_report_repository', buffered_report_repository(original, buffer)), \
            patch.object(CaptureArchiveRepository, 'verify_identity', lambda _: None), \
            patch('project_management.storage.report_drafts.admit', lambda *args: None), \
            patch('project_management.storage.report_draft_preparation_bindings.admit', lambda *args: None), \
            patch('project_management.storage.report_publication_packets.admit', lambda *args: None):
        for index in range(publications):
            if monotonic() >= deadline:
                raise TimeoutError('Bounded scale fixture generation expired.')
            draft = fixture.draft_service.create_authored(
                fixture.actor,
                fixture.project.id,
                fixture.stage.id,
                command_id=draft_command(19000 + index * 10),
                selection=ReportSelection(capture_id=capture_ids[-1]),
                template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
            )
            for revision in range(2, revisions_per_draft + 1):
                draft = fixture.draft_service.save_authored(
                    fixture.actor,
                    fixture.project.id,
                    fixture.stage.id,
                    draft.draft_id,
                    command_id=draft_command(19000 + index * 10 + revision),
                    expected_revision=draft.revision,
                    expected_revision_hash=draft.revision_hash,
                    edits=(),
                )
            publication = fixture.draft_service.finalize_and_commit(
                fixture.actor,
                fixture.project.id,
                fixture.stage.id,
                draft.draft_id,
                command_id=draft_command(19000 + index * 10 + 9),
                expected_revision=draft.revision,
            )
            drafts.append(draft.draft_id)
            publication_ids.append(publication.manifest.publication_id)
            if progress is not None and (index + 1) % 10 == 0:
                progress(index + 1)
    with original(fixture.actor, fixture.project.id, fixture.stage.id, write=True) as repository:
        fast_import_records(repository, buffer.records)
    from project_management.services.report_publication_reads import ReportPublicationReader, prefetch_publications

    packets = []
    for start in range(0, len(publication_ids), 20):
        with fixture.archive._report_read_view(fixture.actor, fixture.project.id, fixture.stage.id) as view:
            selected = publication_ids[start:start + 20]
            prefetch_publications(view, selected)
            packets.extend(ReportPublicationReader(view).read_artifacts(item, fixture.actor.subject) for item in selected)
    return ReportReadFixture(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        ReportQueryService(fixture.archive, fixture.draft_service),
        source_head,
        _digest({'captures': capture_ids, 'drafts': drafts, 'publications': publication_ids, 'head': source_head}),
        tuple(capture_ids),
        tuple(drafts),
        tuple(publication_ids),
        tuple(packets),
    )


def _create_captures(fixture, count: int) -> tuple[str, ...]:
    result = []
    for index in range(count):
        capture_id = f'72000000-0000-4000-8000-{index + 1:012d}'
        intent = CaptureIntent(
            project_id=fixture.project.id,
            stage_id=fixture.stage.id,
            capture_id=capture_id,
            request_id=f'72100000-0000-4000-8000-{index + 1:012d}',
            source=CaptureSourceIdentity(
                'jira',
                'team-jira',
                fixture.stage.descriptor.endpoint,
                f'principal:{fixture.actor.subject}',
                'synthetic-fixture-credential',
                fixture.stage.definition_hash,
            ),
            original_input_hash=f'{index + 1:064x}',
            required_parts=('facts', 'comments'),
            deadline_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        fixture.archive.prepare(fixture.actor, intent)
        pages, items = [], _fixed_items()
        for item in items:
            page = fixture.archive.append_page(fixture.actor, intent, _page(index, item))
            fixture.archive.append_snapshot(fixture.actor, intent, _snapshot(index, item, (page.page_id,)))
            pages.append(page.page_id)
        fixture.archive.finalize(
            fixture.actor,
            intent,
            MembershipInput(items, PartCoverage('complete', 'fixture-source', len(items), len(items), None), tuple(pages)),
            complete=True,
        )
        result.append(capture_id)
    return tuple(result)


def _save_revisions(fixture, draft, index: int, revisions_per_draft: int):
    for revision in range(draft.revision + 1, revisions_per_draft + 1):
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        note = next(row for row in draft.authoring_context['notes'] if row['note_id'] == note_id)
        draft = fixture.draft_service.save_authored(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            draft.draft_id,
            command_id=draft_command(18000 + index * 10 + revision),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(_note_edit(index, revision, note_id, note['body_hash']),),
        )
    return draft


def _fixed_items() -> tuple[WorkItemIdentity, ...]:
    return (
        WorkItemIdentity('jira', 'team-jira', '101', 'ALPHA-101'),
        WorkItemIdentity('jira', 'team-jira', '102', 'ALPHA-102'),
        WorkItemIdentity('jira', 'team-jira', '103', 'ALPHA-103'),
    )


def _fixture_day(index: int) -> str:
    return ('2026-11-02', '2026-11-03', '2026-11-04', '2026-11-09')[index % 4]


def _page(index: int, item: WorkItemIdentity) -> RawPageInput:
    body = json.dumps({'key': item.display_key, 'fixture': 'fixed-three-tickets'}, sort_keys=True).encode('utf-8')
    return RawPageInput(f'facts-{item.stable_id}', item, 'application/json; charset=utf-8', body, f'request-{index}-{item.stable_id}')


def _snapshot(index: int, item: WorkItemIdentity, page_ids: tuple[str, ...]) -> SnapshotInput:
    complete = PartCoverage('complete', 'fixture-source', 1, 1, None)
    return SnapshotInput(
        item,
        {'summary': f'{item.display_key} synthetic fixture facts', 'status': 'Open'},
        {'c1': {'id': 'c1', 'body': f'{item.display_key} retained synthetic comment'}},
        {},
        {},
        {},
        CaptureCoverage(complete, complete, PartCoverage('not_requested', None, None, None, None),
                        PartCoverage('not_requested', None, None, None, None),
                        PartCoverage('not_requested', None, None, None, None)),
        page_ids,
        True,
    )


def _source_hash(snapshot: SnapshotInput) -> str:
    return content_hash({
        'identity': snapshot.identity,
        'facts': snapshot.facts,
        'comments_by_id': snapshot.comments_by_id,
        'history_by_id': snapshot.history_by_id,
        'attachments_by_id': snapshot.attachments_by_id,
        'dependencies_by_id': snapshot.dependencies_by_id,
    })


def _note_edit(index: int, revision: int, note_id: str, expected: str):
    return report_api.AuthoredEditRequest(
        f'73000000-0000-4000-8000-{index * 100 + revision:012d}',
        'note',
        {'scope': 'daily_note', 'note_id': note_id},
        {
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [{
                    'type': 'text',
                    'text': f'Synthetic revision {revision} for fixture {index}.',
                    'marks': [],
                    'foreground': None,
                    'background': None,
                }],
            }],
        },
        expected,
    )


def _digest(value: dict) -> str:
    data = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()
