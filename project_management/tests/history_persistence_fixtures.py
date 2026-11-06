from dataclasses import replace
from datetime import UTC, datetime
import subprocess
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError, ArchiveLimits, ArchiveStorageConfig
from project_management.app.domain.contracts import ProjectActor, ProjectSummary, ScopeDescriptor, ScopeSelection, StageSummary
from project_management.app.domain.report_publication_contracts import PUBLICATION_FILES, publication_path
from project_management.models import Project, ProjectStage
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.services.capture_archive import CaptureArchiveService
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command, draft_selection, valid_source_snapshot
from project_management.tests.report_render_fixtures import safe_snapshot
from project_management.tests.test_report_template_compilation import data_block, matrix_block, slot_block


def history_fixture(tmp_path, *, document=None, reference_verifier=None, actor_subject='archive-owner'):
    actor = ProjectActor(actor_subject)
    project = ProjectSummary(str(uuid4()), 'alpha', 'Alpha', False, datetime.now(UTC))
    descriptor = ScopeDescriptor(
        'jira',
        'alpha-jira',
        'https://tracker.example.test/jira',
        'scope:1',
        'jql',
        'project = ALPHA',
        'query-version-1',
    )
    stage = StageSummary(str(uuid4()), 'release-1', 'Release 1', ScopeSelection('alpha-jira', 1), descriptor, descriptor.definition_hash(), datetime.now(UTC), 'current')
    archive_root = tmp_path / 'history-archive'
    archive_root.mkdir()
    repository_factory = FailingRepositoryFactory()
    archive = CaptureArchiveService(
        ProjectApiStub(project, stage, actor.subject),
        repository_factory,
        ArchiveStorageConfig(archive_root, 'Archive Test', 'archive@example.test', archive_limits()),
    )
    archive.initialize_stage(actor, project.id, stage.id)
    Project.objects.create(id=project.id, owner_subject=actor.subject, key=project.key, name=project.name)
    ProjectStage.objects.create(
        id=stage.id,
        project_id=project.id,
        key=stage.key,
        name=stage.name,
        selection_json={'profile_id': 'alpha-jira', 'revision': 1},
        descriptor_json={'provider_id': 'jira'},
        definition_hash=stage.definition_hash,
    )
    template_service = report_api.ReportTemplateService(clock=FixedClock())
    template = template_service.create(
        actor,
        project.id,
        command_id=draft_command(8001),
        name='Daily matrix',
        document=document or continuity_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    template_selection = report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash)
    source_reader = StaticSourceReader(source_commit=git_head(archive_root, project.id, stage.id), rule_hash=stage.definition_hash)
    continuity = report_api.ReportContinuityService(archive, source_reader, template_service=template_service, clock=FixedClock())
    series = continuity.create_series(
        actor,
        project.id,
        stage.id,
        command_id=draft_command(8002),
        name='Daily PM',
        calendar=calendar(),
        template_selection=template_selection,
    )
    draft_service = report_api.ReportDraftService(
        archive,
        source_reader,
        report_api.ReportRenderer(),
        clock=FixedClock(),
        template_service=template_service,
        reference_verifier=reference_verifier,
    )
    return SimpleNamespace(
        actor=actor,
        project=project,
        stage=stage,
        archive=archive,
        repository_factory=repository_factory,
        archive_root=archive_root,
        continuity=continuity,
        draft_service=draft_service,
        source_reader=source_reader,
        template_service=template_service,
        template_selection=template_selection,
        series=series,
    )


def prepare_daily(fixture, index, day, baseline):
    preparation_id = f'71000000-0000-4000-8000-{index:012d}'
    command_id = draft_command(8002 + index)
    draft_id = str(uuid5(UUID(fixture.stage.id), f'draft:{command_id}'))
    selection = replace(draft_selection(), capture_id=f'72000000-0000-4000-8000-{index:012d}')
    template_request_hash = report_api.authored_create_template_use_request_hash(
        selection,
        fixture.template_selection,
        preparation_id,
    )
    pinned = fixture.template_service.use(
        fixture.actor,
        fixture.project.id,
        command_id=command_id,
        draft_id=draft_id,
        request_hash=template_request_hash,
        selection=fixture.template_selection,
        use_mode='continuity_prepare',
    )
    template_use_hash = report_api.pinned_template_use_hash(pinned)
    context_ref = fixture.continuity.prepare_context(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        preparation_id=preparation_id,
        create_command_id=command_id,
        series_id=fixture.series.series_id,
        series_policy_hash=fixture.series.revision_hash,
        meeting_date=day,
        expected_baseline_ref=baseline,
        selection=selection,
        template_use_hash=template_use_hash,
    )
    return SimpleNamespace(
        preparation_id=preparation_id,
        command_id=command_id,
        selection=selection,
        context_ref=context_ref,
        template_request_hash=template_request_hash,
        template_use_hash=template_use_hash,
        final_create_request_hash=report_api.authored_create_request_hash(
            selection,
            fixture.template_selection,
            preparation_id,
            context_ref.context_hash,
        ),
    )


def create_saved_daily(fixture, daily, index, text, color, save_command):
    draft = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=daily.command_id,
        selection=daily.selection,
        template=fixture.template_selection,
        preparation_id=daily.preparation_id,
    )
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    existing = next((note for note in draft.authoring_context['notes'] if note['note_id'] == note_id), None)
    return fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=save_command,
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(index, note_id, text, color, None if existing is None else existing['body_hash']),),
    )


def continuity_document(*, required_slot=False):
    blocks = [
        data_block('key_messages', 1),
        data_block('changes', 2),
        data_block('register', 3),
        data_block('coverage', 4),
        matrix_block(),
    ]
    if required_slot:
        blocks.insert(0, slot_block(1, fill_mode='manual', required=True))
    return {
        'schema_version': 2,
        'report_kind': 'daily',
        'blocks': blocks,
    }


def weekly_document():
    document = continuity_document()
    document['report_kind'] = 'weekly'
    document['blocks'] = [*document['blocks'], data_block('weekly_timeline', 5)]
    return document


def calendar():
    return report_api.ReportingCalendar(
        'intel-workweek',
        7,
        'Asia/Shanghai',
        'date_map',
        {
            '2026-11-02': {'workweek_year': 2026, 'workweek': 45, 'weekday': 1},
            '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
            '2026-11-04': {'workweek_year': 2026, 'workweek': 45, 'weekday': 3},
            '2026-11-09': {'workweek_year': 2026, 'workweek': 46, 'weekday': 1},
        },
    )


def daily_note_edit(index, note_id, text, foreground, expected):
    return report_api.AuthoredEditRequest(
        f'73000000-0000-4000-8000-{index:012d}',
        'note',
        {'scope': 'daily_note', 'note_id': note_id},
        plain_fragment(text, foreground=foreground),
        expected,
    )


def slot_fill_edit(index, slot_id, text):
    return report_api.AuthoredEditRequest(
        f'73000000-0000-4000-8000-{index:012d}',
        'slot_fill',
        {'scope': 'template_slot', 'slot_id': slot_id},
        plain_fragment(text),
        None,
    )


def plain_fragment(text, *, foreground=None):
    return {
        'schema_version': 2,
        'blocks': [{
            'type': 'paragraph',
            'content': [{
                'type': 'text',
                'text': text,
                'marks': [],
                'foreground': foreground,
                'background': None,
            }],
        }],
    }


def daily_note_reference_edit(index, note_id, option, expected):
    href = option.fragment['blocks'][0]['content'][0]['href']
    return report_api.AuthoredEditRequest(
        f'73000000-0000-4000-8000-{index:012d}',
        'note',
        {'scope': 'daily_note', 'note_id': note_id},
        {
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [{
                    'type': 'link',
                    'href': href,
                    'reference_id': option.reference_id,
                    'content': [{
                        'type': 'text',
                        'text': 'DEMO-101',
                        'marks': [],
                        'foreground': '#0055aa',
                        'background': None,
                    }],
                }],
            }],
        },
        expected,
        (option.receipt,),
    )


def reference_observation(draft):
    row = draft.snapshot.rows[0]
    return report_api.ReferenceObservation(
        identity={
            'provider_id': row.identity.provider_id,
            'endpoint_id': row.identity.endpoint_id,
            'stable_id': row.identity.stable_id,
            'display_key': row.identity.display_key,
        },
        requested_key=row.identity.display_key,
        current_key=row.identity.display_key,
        canonical_url='https://tracker.example.test/jira/browse/' + row.identity.display_key,
        title=row.title,
        assignee={'id': 'dev-a', 'display_name': 'Alice'},
        assignee_state='assigned',
        observed_at='2026-11-03T01:00:00+00:00',
        source_updated_at='2026-11-02T23:59:00+00:00',
        lookup_kind='live',
        scope_snapshot_hash='b' * 64,
    )


def source_snapshot():
    return valid_source_snapshot(
        safe_snapshot(days=()),
        project_id='70000000-0000-4000-8000-000000000001',
        stage_id='70000000-0000-4000-8000-000000000002',
        owner_subject='archive-owner',
        rule_hash='b' * 64,
        source_commit='a' * 40,
        capture_id='72000000-0000-4000-8000-000000000001',
    )


def note_by_id(context, note_id):
    return next(note for note in context['notes'] if note['note_id'] == note_id)


def git_head(root, project_id, stage_id):
    archive = root / 'projects' / project_id / 'stages' / stage_id / 'archive'
    result = subprocess.run(['git', '-C', str(archive), 'rev-parse', 'main'], check=True, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()


def publication_ids(root, project_id, stage_id):
    path = root / 'projects' / project_id / 'stages' / stage_id / 'archive' / 'report_publications'
    if not path.exists():
        return ()
    return tuple(sorted(item.name for item in path.iterdir() if item.is_dir()))


def ref_for(publication):
    return report_api.PublicationRef(publication.manifest.publication_id, publication.manifest_sha256, publication.commit_id)


def publication_file_bytes(fixture, publication):
    repository = fixture.repository_factory.open(
        fixture.archive.config,
        fixture.project,
        fixture.stage,
        fixture.actor.subject,
    )
    return {name: repository.read_file(publication_path(publication.manifest.publication_id, name), publication.commit_id) for name in PUBLICATION_FILES}


def publication_stub(publication_id, meeting_key, finalized_at):
    return SimpleNamespace(
        manifest=SimpleNamespace(
            publication_id=publication_id,
            meeting_key=meeting_key,
            finalized_at=finalized_at,
        )
    )


def archive_limits():
    return ArchiveLimits(
        max_root_bytes=64 * 1024 * 1024,
        max_root_files=10000,
        max_stage_bytes=32 * 1024 * 1024,
        max_stage_files=5000,
        max_capture_bytes=8 * 1024 * 1024,
        max_capture_files=1000,
        max_raw_page_bytes=1024 * 1024,
        max_object_bytes=2 * 1024 * 1024,
    )


class FailingRepositoryFactory:
    def __init__(self):
        self.inner = LocalArchiveRepositoryFactory()
        self.fail_append_once = False

    def open(self, config, project, stage, owner_subject):
        repository = self.inner.open(config, project, stage, owner_subject)
        original = repository.append_record

        def append_record(*args, **kwargs):
            if self.fail_append_once:
                self.fail_append_once = False
                raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
            return original(*args, **kwargs)

        repository.append_record = append_record
        return repository


def weekly_view_context():
    return {
        'schema_version': 1,
        'series_id': '75000000-0000-4000-8000-000000000001',
        'series_policy_revision': 1,
        'series_policy_hash': '1' * 64,
        'report_role': 'weekly_view',
        'meeting': None,
        'period': {'calendar_id': 'intel-workweek', 'calendar_revision': 7, 'workweek_year': 2026, 'workweek': 45},
        'base_daily_publication': None,
        'baseline_choice': 'previous_final',
        'acknowledged_gap_draft_ids': (),
        'row_order': {'revision': 1, 'group_order': (), 'rows': ()},
        'weekly_seed': {
            'baseline': None,
            'note_refs': (),
            'unresolved_action_ids': (),
            'persistent_note_refs': (),
            'earlier_period_refs': (),
        },
        'notes': (),
        'current_observations': (),
        'actions': (),
        'persistent_notes': (),
        'selected_daily_publications': ({
            'publication_id': '74000000-0000-4000-8000-000000000001',
            'manifest_hash': '2' * 64,
            'commit': '3' * 40,
        },),
    }
