from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.test import TestCase, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import ArchiveError, CapturePage, CaptureReceipt
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_project_report_views import FastUiArchive


class PagedArchive(FastUiArchive):
    def list_captures(self, actor, project_id, stage_id, *, limit=100, after=None):
        self._stage_for_read(actor, project_id, stage_id)
        if after not in {None, 'cursor-20'}:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        start = 20 if after == 'cursor-20' else 0
        count = 1 if start else 20
        items = tuple(
            CaptureReceipt(
                f'99999999-9999-4999-8999-{index:012d}',
                self.repository.head(),
                '1' * 64,
                None,
                True,
                True,
                None,
                (),
                'current',
            )
            for index in range(start, start + count)
        )
        return CapturePage(items, None if start else 'cursor-20')


class PagedReportService:
    def list_drafts(self, actor, project_id, stage_id, *, limit=20, offset=0):
        count = 1 if offset else 20
        items = tuple(
            report_api.ReportDraftSummary(
                f'aaaaaaaa-aaaa-4aaa-8aaa-{index:012d}',
                1,
                '2' * 64,
                '2026-11-02T01:00:00+00:00',
                '2026-11-02T02:00:00+00:00',
                'draft',
                'daily-standup',
                None,
            )
            for index in range(offset, offset + count)
        )
        return report_api.ReportDraftPage(items, None if offset else 20)

    def list_publications(self, actor, project_id, stage_id, *, limit=20, offset=0):
        count = 1 if offset else 20
        items = tuple(
            SimpleNamespace(
                manifest=SimpleNamespace(
                    publication_id=f'bbbbbbbb-bbbb-4bbb-8bbb-{index:012d}',
                    draft_revision=1,
                    source_as_of='2026-11-02T01:00:00+00:00',
                    finalized_at='2026-11-02T03:00:00+00:00',
                ),
                commit_id='3' * 40,
            )
            for index in range(offset, offset + count)
        )
        return report_api.ReportPublicationPage(items, None if offset else 20)


class CorruptReportService(PagedReportService):
    def list_drafts(self, actor, project_id, stage_id, *, limit=20, offset=0):
        raise report_api.ReportError('REPORT_ARTIFACT_INVALID')


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectReportStagePagination(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = PagedArchive(Path(self.temporary.name) / 'paged-reporting-archive')
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage

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

    def install_facade(self, facade, *views):
        originals = [view.facade_factory for view in views]
        for view in views:
            view.facade_factory = staticmethod(lambda facade=facade: facade)
        self.addCleanup(lambda: [setattr(view, 'facade_factory', original)
                                 for view, original in zip(views, originals)])

    def test_shouldKeepListRowsWhenMoreCaptureDraftAndPublicationPagesExist(self):
        from ui_web.facades.project_reports import ProjectReportFacade
        from ui_web.views import project_reports

        facade = ProjectReportFacade(
            ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            PagedReportService(),
            self.archive,
        )
        self.install_facade(facade, project_reports.ProjectStageReportView)

        first = self.client.get(self.stage_url(), **self.auth('alice'))
        second = self.client.get(
            self.stage_url() + '?capture_after=cursor-20&draft_offset=20&publication_offset=20',
            **self.auth('alice'),
        )
        invalid = self.client.get(self.stage_url() + '?draft_offset=-1', **self.auth('alice'))

        first_content = first.content.decode('utf-8')
        second_content = second.content.decode('utf-8')
        self.assertEqual(200, first.status_code)
        self.assertIn('99999999-9999-4999-8999-000000000000', first_content)
        self.assertIn('Next captures', first_content)
        self.assertIn('Next drafts', first_content)
        self.assertIn('Next publications', first_content)
        self.assertIn('Select capture', first_content)
        self.assertEqual(200, second.status_code)
        self.assertIn('99999999-9999-4999-8999-000000000020', second_content)
        self.assertIn('aaaaaaaa-aaaa-4aaa-8aaa-000000000020', second_content)
        self.assertIn('bbbbbbbb-bbbb-4bbb-8bbb-000000000020', second_content)
        self.assertIn('Previous drafts', second_content)
        self.assertIn('Previous publications', second_content)
        self.assertEqual(400, invalid.status_code)

    def test_shouldCreateDraftFromPageTwoCaptureAndRejectTamperedCursor(self):
        from ui_web.facades.project_reports import ProjectReportFacade
        from ui_web.views import project_reports

        source = StaticSourceReader(rule_hash=self.stage.definition_hash)
        service = report_api.ReportDraftService(
            self.archive,
            source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
        )
        facade = ProjectReportFacade(
            ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            service,
            self.archive,
        )
        self.install_facade(facade, project_reports.ProjectStageReportView, project_reports.ReportDraftCreateView)

        page_two_capture = '99999999-9999-4999-8999-000000000020'
        created = self.client.post(self.create_url(), {
            'command_id': draft_command(470),
            'capture_after': 'cursor-20',
            'capture_id': page_two_capture,
            'template_id': 'daily-standup',
            'template_version': '1',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))
        tampered = self.client.post(self.create_url(), {
            'command_id': draft_command(471),
            'capture_after': 'tampered',
            'capture_id': page_two_capture,
            'template_id': 'daily-standup',
            'template_version': '1',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))

        self.assertEqual(302, created.status_code)
        self.assertEqual(page_two_capture, source.selections[0].capture_id)
        self.assertEqual(400, tampered.status_code)

    def test_shouldRenderUnconfiguredButSurfaceCorruptReportStoreAsError(self):
        from ui_web.facades.project_reports import ProjectReportFacade
        from ui_web.views import project_reports

        project_api = ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject)
        factories = [
            ProjectReportFacade(project_api, None, None),
            ProjectReportFacade(project_api, CorruptReportService(), self.archive),
        ]
        original = project_reports.ProjectStageReportView.facade_factory
        project_reports.ProjectStageReportView.facade_factory = staticmethod(lambda: factories.pop(0))
        self.addCleanup(lambda: setattr(project_reports.ProjectStageReportView, 'facade_factory', original))

        unconfigured = self.client.get(self.stage_url(), **self.auth('alice'))
        corrupt = self.client.get(self.stage_url(), **self.auth('alice'))

        self.assertEqual(200, unconfigured.status_code)
        self.assertIn('Report archive is not configured.', unconfigured.content.decode('utf-8'))
        self.assertEqual(400, corrupt.status_code)
        self.assertIn('Report artifact is invalid.', corrupt.content.decode('utf-8'))
