from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import CapturePage, CaptureReceipt
from project_management.app.domain.capture_values import sha256_bytes
from project_management.app.domain.contracts import ProjectActor
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command
from project_management.tests.report_render_fixtures import daily_template, source_key_hash
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


class FastUiArchive(DraftArchive):
    def __init__(self, root: Path):
        super().__init__(root)
        self.actor = ProjectActor('basic:alice')
        self.repository.owner_subject = self.actor.subject
        self.capture_id = '99999999-9999-4999-8999-999999999999'

    def list_captures(self, actor, project_id, stage_id, *, limit=100, after=None):
        self._stage_for_read(actor, project_id, stage_id)
        return CapturePage((
            CaptureReceipt(
                self.capture_id,
                self.repository.head(),
                '1' * 64,
                None,
                True,
                True,
                None,
                (),
                'current',
            ),
        ), None)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectReportViews(CaptureArchiveScenario, ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = FastUiArchive(Path(self.temporary.name) / 'project-reporting-archive')
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage
        self.source = StaticSourceReader(rule_hash=self.stage.definition_hash)
        self.service = report_api.ReportDraftService(
            self.archive,
            self.source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
        )
        self.capture_id = self.archive.capture_id
        self.facade = None

    def report_facade(self):
        from ui_web.facades.project_reports import ProjectReportFacade

        if self.facade is None:
            self.facade = ProjectReportFacade(ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
                                              self.service, self.archive)
        return self.facade

    def with_report_facade(self):
        from ui_web.views import project_reports

        classes = [
            project_reports.ProjectStageReportView,
            project_reports.ReportDraftCreateView,
            project_reports.ReportDraftEditView,
            project_reports.ReportDraftSaveView,
            project_reports.ReportDraftRenderView,
            project_reports.ReportDraftDownloadView,
            project_reports.ReportDraftClipboardView,
            project_reports.ReportDraftFinalizeView,
            project_reports.ReportDraftResumeView,
            project_reports.ReportPublicationView,
            project_reports.ReportPublicationRevisionView,
            project_reports.ReportPublicationDownloadView,
        ]
        originals = [view.facade_factory for view in classes]
        for view in classes:
            view.facade_factory = staticmethod(self.report_facade)
        self.addCleanup(lambda: [setattr(view, 'facade_factory', original)
                                 for view, original in zip(classes, originals)])

    def stage_url(self):
        return reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def create_url(self):
        return reverse('ui_web:report_draft_create', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def editor_url(self, draft_id):
        return reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def save_url(self, draft_id):
        return reverse('ui_web:report_draft_save', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def render_url(self, draft_id, revision):
        return reverse('ui_web:report_draft_render', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        }) + f'?revision={revision}'

    def download_url(self, draft_id, revision, format='html'):
        return reverse('ui_web:report_draft_download', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        }) + f'?revision={revision}&format={format}'

    def clipboard_url(self, draft_id, revision):
        return reverse('ui_web:report_draft_clipboard', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        }) + f'?revision={revision}'

    def finalize_url(self, draft_id):
        return reverse('ui_web:report_draft_finalize', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def publication_url(self, publication_id):
        return reverse('ui_web:report_publication', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'publication_id': publication_id,
        })

    def publication_download_url(self, publication_id, format='html'):
        return reverse('ui_web:report_publication_download', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'publication_id': publication_id,
        }) + f'?format={format}'

    def resume_url(self, draft_id):
        return reverse('ui_web:report_draft_resume', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def revision_url(self, publication_id):
        return reverse('ui_web:report_publication_revision', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'publication_id': publication_id,
        })

    def create_draft(self):
        response = self.client.post(self.create_url(), {
            'command_id': draft_command(400),
            'capture_id': self.capture_id,
            'template_id': 'daily-standup',
            'template_version': '1',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))
        draft_id = response['Location'].rstrip('/').rsplit('/', 1)[-1]
        return draft_id, response

    def test_shouldOpenStageReportWorkbenchAndCreateDraftThroughPublicService(self):
        self.with_report_facade()

        missing_auth = self.client.get(self.stage_url())
        stage = self.client.get(self.stage_url(), **self.auth('alice'))
        created_draft_id, created = self.create_draft()
        editor = self.client.get(self.editor_url(created_draft_id), **self.auth('alice'))

        self.assertEqual(401, missing_auth.status_code)
        self.assertEqual(200, stage.status_code)
        content = stage.content.decode('utf-8')
        self.assertIn('Report workbench', content)
        self.assertIn(self.capture_id, content)
        self.assertIn('Run stage report', content)
        self.assertIn('Runtime disabled', content)
        self.assertIn('disabled', content)
        self.assertEqual(302, created.status_code)
        self.assertEqual(200, editor.status_code)
        self.assertEqual(1, self.source.calls)

    def test_shouldReturnWrongOwner404BeforeSourceLookup(self):
        self.with_report_facade()

        response = self.client.post(self.create_url(), {
            'command_id': draft_command(401),
            'capture_id': self.capture_id,
            'template_id': 'daily-standup',
            'template_version': '1',
            'timezone': 'UTC',
            'purpose': 'standup',
        }, **self.auth('bob'))

        self.assertEqual(404, response.status_code)
        self.assertEqual(0, self.source.calls)

    def test_shouldSaveRenderClipboardDownloadAndFinalizeExactRevision(self):
        self.with_report_facade()
        draft_id, created = self.create_draft()
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        row = draft.snapshot.rows[0]
        source_hash = source_key_hash(row.source_key)

        saved_response = self.client.post(self.save_url(draft_id), {
            'command_id': draft_command(402),
            'expected_revision': '1',
            'template_id': 'daily-standup',
            'template_version': '1',
            'note_edit_id': '11111111-1111-4111-8111-111111111111',
            'note_target': 'report',
            'note_text': '会议 note for release readiness.',
            'override_edit_id': '22222222-2222-4222-8222-222222222222',
            'override_target': f'issue:{source_hash}:what',
            'override_text': 'Edited narrative override for the saved draft.',
        }, **self.auth('alice'))
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        render = self.client.get(self.render_url(draft_id, saved.revision), **self.auth('alice'))
        download = self.client.get(self.download_url(draft_id, saved.revision), **self.auth('alice'))
        clipboard = self.client.get(self.clipboard_url(draft_id, saved.revision), **self.auth('alice')).json()
        stale = self.client.post(self.save_url(draft_id), {
            'command_id': draft_command(403),
            'expected_revision': '1',
            'template_id': 'daily-standup',
            'template_version': '1',
            'note_edit_id': '33333333-3333-4333-8333-333333333333',
            'note_target': 'report',
            'note_text': 'stale note',
        }, **self.auth('alice'))
        finalized = self.client.post(self.finalize_url(draft_id), {
            'command_id': draft_command(404),
            'expected_revision': str(saved.revision),
            'confirm': 'on',
        }, **self.auth('alice'))
        publication_id = finalized['Location'].rstrip('/').rsplit('/', 1)[-1]
        publication_download = self.client.get(self.publication_download_url(publication_id), **self.auth('alice'))
        finalized_editor = self.client.get(self.editor_url(draft_id), **self.auth('alice')).content.decode('utf-8')

        self.assertEqual(302, created.status_code)
        self.assertEqual(302, saved_response.status_code)
        self.assertEqual(200, render.status_code)
        self.assertEqual('nosniff', render['X-Content-Type-Options'])
        self.assertIn('sandbox', render['Content-Security-Policy'])
        self.assertIn(b'Edited narrative override for the saved draft.', render.content)
        self.assertEqual(render.content, download.content)
        self.assertIn('attachment;', download['Content-Disposition'])
        self.assertEqual(saved.revision_hash, clipboard['revision_hash'])
        self.assertEqual(saved.revision, clipboard['revision'])
        self.assertEqual(sha256_bytes(clipboard['html_fragment'].encode('utf-8')), clipboard['html_sha256'])
        self.assertEqual(sha256_bytes(clipboard['plain_text'].encode('utf-8')), clipboard['plain_sha256'])
        self.assertEqual(409, stale.status_code)
        self.assertEqual(302, finalized.status_code)
        self.assertNotIn('data-report-save-form', finalized_editor)
        self.assertNotIn('Finalize and commit', finalized_editor)
        self.assertEqual(publication_download.content, self.service.read_artifact(
            self.actor,
            self.project.id,
            self.stage.id,
            publication_id,
            'html',
        ))

    def test_shouldPreserveMultipleNotesAndOverridesUnlessExplicitlyRemoved(self):
        self.with_report_facade()
        draft_id, _ = self.create_draft()
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        row = draft.snapshot.rows[0]
        source_hash = source_key_hash(row.source_key)
        action_target = f'action:{source_hash}:{row.summary_ref.summary_id}:0'

        first_save = self.client.post(self.save_url(draft_id), {
            'command_id': draft_command(430),
            'expected_revision': '1',
            'template_id': 'daily-standup',
            'template_version': '1',
            'edit_id': [
                '10000000-0000-4000-8000-000000000001',
                '10000000-0000-4000-8000-000000000002',
                '10000000-0000-4000-8000-000000000003',
                '20000000-0000-4000-8000-000000000001',
                '20000000-0000-4000-8000-000000000002',
            ],
            'edit_kind': ['note', 'note', 'note', 'narrative_override', 'narrative_override'],
            'edit_target': ['report', f'issue:{source_hash}', action_target, f'issue:{source_hash}:what',
                            f'issue:{source_hash}:verification'],
            'edit_text': ['report note', 'issue note', 'action note', 'what override', 'verification override'],
            'edit_operation': ['add', 'add', 'add', 'add', 'add'],
        }, **self.auth('alice'))
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)

        second_save = self.client.post(self.save_url(draft_id), {
            'command_id': draft_command(431),
            'expected_revision': str(saved.revision),
            'template_id': 'daily-standup',
            'template_version': '1',
            'edit_id': [
                '10000000-0000-4000-8000-000000000002',
                '20000000-0000-4000-8000-000000000001',
            ],
            'edit_kind': ['note', 'narrative_override'],
            'edit_target': [f'issue:{source_hash}', f'issue:{source_hash}:what'],
            'edit_text': ['issue note edited', ''],
            'edit_operation': ['keep', 'remove'],
        }, **self.auth('alice'))
        edited = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        by_id = {edit.edit_id: edit for edit in edited.edits}

        self.assertEqual(302, first_save.status_code)
        self.assertEqual(302, second_save.status_code)
        self.assertEqual(5, len(saved.edits))
        self.assertEqual(4, len(edited.edits))
        self.assertEqual('report note', by_id['10000000-0000-4000-8000-000000000001'].text)
        self.assertEqual('issue note edited', by_id['10000000-0000-4000-8000-000000000002'].text)
        self.assertEqual('action note', by_id['10000000-0000-4000-8000-000000000003'].text)
        self.assertEqual('verification override', by_id['20000000-0000-4000-8000-000000000002'].text)
        self.assertNotIn('20000000-0000-4000-8000-000000000001', by_id)

    def test_shouldProtectWriteRoutesWithCsrfAndRejectMalformedQueries(self):
        self.with_report_facade()
        csrf_client = Client(enforce_csrf_checks=True)
        draft_id, _ = self.create_draft()

        posts = [
            (self.create_url(), {'command_id': draft_command(410)}),
            (self.save_url(draft_id), {'command_id': draft_command(411), 'expected_revision': '1'}),
            (self.finalize_url(draft_id), {'command_id': draft_command(412), 'expected_revision': '1', 'confirm': 'on'}),
        ]

        for path, payload in posts:
            with self.subTest(path=path):
                response = csrf_client.post(path, payload, **self.auth('alice'))
                self.assertEqual(403, response.status_code)

        malformed_render = self.client.get(
            reverse('ui_web:report_draft_render', kwargs={
                'project_id': self.project.id,
                'stage_id': self.stage.id,
                'draft_id': draft_id,
            }) + '?revision=-1',
            **self.auth('alice'),
        )
        malformed_download = self.client.get(self.download_url(draft_id, 1, 'json'), **self.auth('alice'))

        self.assertEqual(400, malformed_render.status_code)
        self.assertEqual(400, malformed_download.status_code)
        self.assertEqual(405, self.client.get(self.create_url(), **self.auth('alice')).status_code)
        self.assertEqual(405, self.client.get(self.save_url(draft_id), **self.auth('alice')).status_code)
        self.assertEqual(405, self.client.get(self.finalize_url(draft_id), **self.auth('alice')).status_code)

    def test_shouldExposeResumeFinalizationAndCreateLinkedPublicationRevision(self):
        self.with_report_facade()
        draft_id, _ = self.create_draft()
        self.archive.repository.fail_append_once = True
        failed_finalize = self.client.post(self.finalize_url(draft_id), {
            'command_id': draft_command(450),
            'expected_revision': '1',
            'confirm': 'on',
        }, **self.auth('alice'))
        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        wrong_resume = self.client.post(self.resume_url(draft_id), {
            'command_id': draft_command(999),
        }, **self.auth('alice'))
        resumed = self.client.post(self.resume_url(draft_id), {
            'command_id': draft_command(450),
        }, **self.auth('alice'))
        publication_id = resumed['Location'].rstrip('/').rsplit('/', 1)[-1]
        publication = self.client.get(self.publication_url(publication_id), **self.auth('alice'))
        revision = self.client.post(self.revision_url(publication_id), {
            'command_id': draft_command(451),
            'template_id': 'daily-standup',
            'template_version': '1',
        }, **self.auth('alice'))
        revision_draft_id = revision['Location'].rstrip('/').rsplit('/', 1)[-1]
        revision_draft = self.service.get(self.actor, self.project.id, self.stage.id, revision_draft_id)
        historical = self.service.create(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(452),
            selection=report_api.ReportSelection(
                capture_id=self.capture_id,
                purpose='historical_export',
                timezone='Asia/Shanghai',
            ),
            template=daily_template(),
        )
        historical_publication = self.service.finalize_and_commit(
            self.actor,
            self.project.id,
            self.stage.id,
            historical.draft_id,
            command_id=draft_command(453),
            expected_revision=1,
        )
        unsupported_revision = self.client.post(self.revision_url(historical_publication.manifest.publication_id), {
            'command_id': draft_command(454),
            'template_id': 'daily-standup',
            'template_version': '1',
        }, **self.auth('alice'))

        self.assertEqual(400, failed_finalize.status_code)
        self.assertIn('Resume finalization', editor.content.decode('utf-8'))
        self.assertEqual(409, wrong_resume.status_code)
        self.assertEqual(302, resumed.status_code)
        self.assertEqual(200, publication.status_code)
        self.assertIn('Create revision', publication.content.decode('utf-8'))
        self.assertEqual(302, revision.status_code)
        self.assertEqual(publication_id, revision_draft.parent_publication_id)
        self.assertEqual(409, unsupported_revision.status_code)

    def test_shouldSwitchLanguageBackToReportGetRoutesWithoutSavingUnsavedFields(self):
        self.with_report_facade()
        draft_id, _ = self.create_draft()
        before = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)

        switch_editor = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': self.editor_url(draft_id)},
            **self.auth('alice'),
        )
        switch_save = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': self.save_url(draft_id)},
            **self.auth('alice'),
        )
        after = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)

        self.assertEqual(self.editor_url(draft_id), switch_editor['Location'])
        self.assertEqual(self.editor_url(draft_id), switch_save['Location'])
        self.assertEqual(before.revision_hash, after.revision_hash)

    def test_shouldRenderActualChineseReportLabelsAndArchiveTarget(self):
        self.with_report_facade()
        self.client.cookies['django_language'] = 'zh-hans'
        stage = self.client.get(self.stage_url(), **self.auth('alice'))
        draft_id, _ = self.create_draft()
        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        draft_context = editor.content.decode('utf-8')

        self.assertEqual(200, stage.status_code)
        self.assertIn('报告工作台', stage.content.decode('utf-8'))
        self.assertEqual(200, editor.status_code)
        self.assertIn('发布目标', draft_context)
        self.assertIn(self.archive.root_id, draft_context)
        self.assertIn(self.project.id, draft_context)
        self.assertIn(self.stage.id, draft_context)
        self.assertNotIn(str(self.archive.root), draft_context)
