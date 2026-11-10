from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import ArchiveError, CapturePage, CaptureReceipt
from project_management.app.api.report_queries import ReportWorkspaceQuery
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command
from project_management.tests.report_render_fixtures import daily_template
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
        self.source = StaticSourceReader(rule_hash=self.stage.definition_hash)
        self.service = report_api.ReportDraftService(
            self.archive,
            self.source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
        )

    def report_facade(self):
        from ui_web.facades.project_reports import ProjectReportFacade

        return ProjectReportFacade(
            ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            self.service,
            self.archive,
        )

    def seed_finalized_reports(self, count):
        draft_ids, publication_ids = [], []
        for index in range(count):
            draft = self.service.create(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(500 + index),
                selection=report_api.ReportSelection(
                    capture_id='99999999-9999-4999-8999-000000000000',
                    purpose='historical_export',
                    timezone='Asia/Shanghai',
                ),
                template=daily_template(),
            )
            publication = self.service.finalize_and_commit(
                self.actor,
                self.project.id,
                self.stage.id,
                draft.draft_id,
                command_id=draft_command(600 + index),
                expected_revision=1,
            )
            draft_ids.append(draft.draft_id)
            publication_ids.append(publication.manifest.publication_id)
        return sorted(draft_ids), sorted(publication_ids)

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

    def test_shouldKeepListRowsWhenMoreCaptureDraftAndPublicationPagesExist(self):
        from ui_web.views import project_reports

        draft_ids, publication_ids = self.seed_finalized_reports(2)
        self.patch_view_factory(self.report_facade, project_reports.ProjectStageReportView)

        # A one-row page lets two real reports exercise next/previous links without seeding a full page.
        with patch('ui_web.facades.project_reports.ReportWorkspaceQuery', partial(ReportWorkspaceQuery, page_size=1)):
            first = self.client.get(self.stage_url(), **self.auth('alice'))
            second = self.client.get(
                self.stage_url() + '?capture_after=cursor-20&draft_offset=1&publication_offset=1',
                **self.auth('alice'),
            )
            invalid = self.client.get(self.stage_url() + '?draft_offset=-1', **self.auth('alice'))

        first_content = first.content.decode('utf-8')
        second_content = second.content.decode('utf-8')
        self.assertEqual(200, first.status_code)
        self.assertIn('99999999-9999-4999-8999-000000000000', first_content)
        self.assertIn(draft_ids[0], first_content)
        self.assertIn(publication_ids[0], first_content)
        self.assertIn('Next captures', first_content)
        self.assertIn('Next drafts', first_content)
        self.assertIn('Next publications', first_content)
        self.assertIn('Select capture', first_content)
        self.assertEqual(200, second.status_code)
        self.assertIn('99999999-9999-4999-8999-000000000020', second_content)
        self.assertIn(draft_ids[1], second_content)
        self.assertIn(publication_ids[1], second_content)
        self.assertIn('Previous drafts', second_content)
        self.assertIn('Previous publications', second_content)
        self.assertEqual(400, invalid.status_code)

    def test_shouldCreateDraftFromPageTwoCaptureAndRejectTamperedCursor(self):
        from ui_web.views import project_reports

        self.patch_view_factory(self.report_facade, project_reports.ProjectStageReportView,
                                project_reports.ReportDraftCreateView)

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
        self.assertEqual(page_two_capture, self.source.selections[0].capture_id)
        self.assertEqual(400, tampered.status_code)

    def test_shouldRenderUnconfiguredButSurfaceCorruptReportStoreAsError(self):
        from ui_web.facades.project_reports import ProjectReportFacade
        from ui_web.views import project_reports

        (self.archive.repository.runtime / 'report-drafts' / 'not-a-report-id').mkdir(parents=True)
        project_api = ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject)
        factories = [
            ProjectReportFacade(project_api, None, None),
            self.report_facade(),
        ]
        self.patch_view_factory(lambda: factories.pop(0), project_reports.ProjectStageReportView)

        unconfigured = self.client.get(self.stage_url(), **self.auth('alice'))
        corrupt = self.client.get(self.stage_url(), **self.auth('alice'))

        self.assertEqual(200, unconfigured.status_code)
        self.assertIn('Report archive is not configured.', unconfigured.content.decode('utf-8'))
        self.assertEqual(400, corrupt.status_code)
        self.assertIn('Report artifact is invalid.', corrupt.content.decode('utf-8'))
