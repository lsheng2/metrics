from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.report_sources import ReportSourceReader
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.summary_fixtures import PACK_ROOT
from ui_web.facades.project_reports import ProjectReportFacade
from ui_web.tests import ui_geometry_contract as geometry
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_report_daily_ui_views import choice, patch_default_facade, seed_retained_capture
from ui_web.tests.test_report_template_browser import project_page


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportQueryBrowser(StaticLiveServerTestCase):
    def test_language_and_lean_commands_keep_the_real_editor_usable(self):
        with TemporaryDirectory() as temporary, pytest.MonkeyPatch.context() as monkeypatch:
            fixture = history_fixture(Path(temporary), actor_subject='basic:alice')
            capture = seed_retained_capture(fixture)
            reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
            fixture.draft_service.source_reader = reader
            fixture.continuity.source_reader = reader
            evidence = Path('.tmp/dashboard-read-performance-20261106') / f'mounted-{uuid4()}'
            evidence.mkdir(parents=True)
            url = self.live_server_url + reverse('ui_web:project_stage_reports', kwargs={
                'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            })

            def unrelated_history(*args, **kwargs):
                raise AssertionError('A daily command rebuilt the report workbench')

            with patch_default_facade(monkeypatch, fixture), project_page(url) as page:
                page.set_default_timeout(15000)
                page.set_default_navigation_timeout(30000)
                for language in ('zh-hans', 'en'):
                    page.locator('select[name="language"]').select_option(language)
                    with page.expect_navigation(wait_until='domcontentloaded'):
                        page.locator('form[action$="/projects/language/"] button').click()
                    self.assertEqual(language, page.locator('html').get_attribute('lang'))
                    self.assertIn(capture, page.locator('article').inner_text())
                monkeypatch.setattr(ProjectReportFacade, 'stage_context', unrelated_history)
                preview = page.locator('[data-report-daily-preview-form]')
                preview.locator('[name="series_id"]').select_option(fixture.series.series_id)
                preview.locator('[name="meeting_date"]').fill('2026-11-02')
                preview.locator('[name="template_choice"]').select_option(choice(fixture.template_selection))
                with page.expect_navigation(wait_until='domcontentloaded'):
                    preview.locator('[data-report-daily-preview]').click()
                self.assertEqual(1, page.locator('[data-report-preparation-page]').count())
                page.locator('[data-report-daily-prepare-form] select[name="capture_id"]').select_option(capture)
                with page.expect_navigation(wait_until='domcontentloaded'):
                    page.locator('[data-report-daily-generate]').click()
                editor_url = page.url
                region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
                region.locator('[data-report-editor-surface]').click()
                editor = region.locator('.ProseMirror')
                editor.fill('Read optimization preserves human notes.')
                editor.press('Control+a')
                page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
                with page.expect_response('**/save/') as pending:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, pending.value.status, pending.value.text())
                self.assertEqual(2, pending.value.json()['revision'])
                page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
                page.goto(editor_url, wait_until='domcontentloaded')
                region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
                self.assertIn('Read optimization preserves human notes.', region.inner_text())
                self.assertEqual('rgb(170, 0, 0)', region.locator('[style*="color"]').first.evaluate(
                    '(node) => getComputedStyle(node).color',
                ))
                page.screenshot(path=str(evidence / 'editor-desktop.png'))
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(evidence / 'editor-mobile.png'))
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), geometry.REPORT_PHONE_PAGE_WIDTH_MAX)
                page.locator('[data-report-finalize-confirm]').check()
                with page.expect_navigation(wait_until='domcontentloaded'):
                    page.locator('[data-report-finalize-button]').click()
                self.assertIn('/publications/', page.url)
                publication_id = page.url.rstrip('/').rsplit('/', 1)[-1]
                with page.expect_download() as download:
                    page.locator('a[href*="/download/"][href*="format=html"]').click()
                path = evidence / 'published.html'
                download.value.save_as(str(path))
                publication = fixture.draft_service.read_publication_artifacts(
                    fixture.actor, fixture.project.id, fixture.stage.id, publication_id,
                )
                self.assertEqual(publication.files['report.html'], path.read_bytes())
                self.assertIn(b'Read optimization preserves human notes.', path.read_bytes())
