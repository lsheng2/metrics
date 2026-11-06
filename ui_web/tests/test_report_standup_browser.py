import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.report_draft_fixtures import draft_command
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page
from ui_web.views.report_exports import ReportDraftExportView, ReportPublicationExportView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestStandupPresentationBrowser(ReportHistoryUiBrowserSupport):
    def setUp(self):
        super().setUp()
        for view in (ReportDraftExportView, ReportPublicationExportView):
            patcher = patch.object(view, 'facade_factory', staticmethod(self.report_facade))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_shouldCreateEditPublishAndDownloadSeparateBodyAndAudit(self):
        directory = Path('.tmp/dashboard-presentation-20261106') / f'browser-{uuid4()}'
        directory.mkdir(parents=True)
        library = self.live_server_url + reverse('ui_web:report_templates', kwargs={'project_id': self.project.id})
        template_id = self.create_standup_template(library)
        template = self.template_service.get(self.actor, self.project.id, template_id, revision=2)
        self.assertEqual('standup/1', template.document['presentation_profile'])
        template_selection = report_api.UserTemplateSelection(template_id, template.revision, template.revision_hash)
        series = self.continuity_service.create_series(
            self.actor, self.project.id, self.stage.id, command_id=draft_command(12001), name='Concise series',
            calendar=report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}),
            template_selection=template_selection,
        )
        draft = self.prepared_continuity_draft(
            setup={'series': series, 'template_selection': template_selection}, command_index=12002,
        )
        with project_page(self.editor_url(draft.draft_id)) as page:
            page.set_default_timeout(15000)
            self.edit_publish_and_download(page, draft, template_id, directory)

    def create_standup_template(self, library):
        with project_page(library) as page:
            page.set_default_timeout(15000)
            create = page.locator('form:has(input[name="action"][value="standup_daily"])')
            with page.expect_navigation():
                create.locator('button[type="submit"]').click()
            root = page.locator('[data-template-builder]')
            self.assertEqual('standup/1', root.get_attribute('data-template-presentation-profile'))
            page.locator('[data-template-add="content"]').click()
            row = page.locator('[data-template-row]').last
            row.locator('[data-template-editor-surface]').click()
            row.locator('.ProseMirror').wait_for()
            row.locator('.ProseMirror').fill('Standup decisions')
            with page.expect_navigation():
                page.locator('[data-template-save-button]').click()
            self.assertEqual('standup/1', page.locator('[data-template-builder]').get_attribute('data-template-presentation-profile'))
            return page.url.rstrip('/').rsplit('/', 1)[-1]

    def edit_publish_and_download(self, page, draft, template_id, directory):
        region = page.locator('[data-continuity-current-note-id] [data-report-wysiwyg-region]').first
        region.locator('[data-report-editor-surface]').click()
        editor = region.locator('.ProseMirror')
        editor.wait_for()
        editor.fill('Validation passed. AR: @Bob confirm release.')
        editor.press('Control+A')
        page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
        self.assertTrue(page.locator('[data-report-finalize-button]').is_disabled())
        with page.expect_response('**/save/') as saved_response:
            page.locator('[data-report-save-button]').click()
        self.assertEqual(200, saved_response.value.status, saved_response.value.text())
        page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
        page.goto(self.editor_url(draft.draft_id), wait_until='domcontentloaded')
        self.assertEqual(0, page.locator('[data-report-export-format] option[value="audit_zip"]').count())
        page.screenshot(path=str(directory / 'editor.png'), full_page=True)
        for format_name, filename in (('markdown', 'draft.md'), ('xlsx', 'draft.xlsx')):
            page.locator('[data-report-export-format]').select_option(format_name)
            with page.expect_download() as pending:
                page.locator('[data-report-export-link]').click()
            pending.value.save_as(directory / filename)
        page.locator('[data-report-finalize-confirm]').check()
        with page.expect_navigation():
            page.locator('[data-report-finalize-button]').click()
        publication_id = page.url.rstrip('/').rsplit('/', 1)[-1]
        with page.expect_download() as pending:
            page.get_by_role('link', name='Download HTML', exact=True).click()
        pending.value.save_as(directory / 'report.html')
        page.locator('[data-report-export-format]').select_option('audit_zip')
        with page.expect_download() as pending:
            page.locator('[data-report-export-link]').click()
        pending.value.save_as(directory / 'audit.zip')
        with ZipFile(directory / 'audit.zip') as archive:
            self.assertEqual((directory / 'report.html').read_bytes(), archive.read('report.html'))
            self.assertIn('Validation passed.', archive.read('edits.json').decode())
            self.assertEqual(8, len(archive.namelist()))
        body = (directory / 'report.html').read_text(encoding='utf-8')
        text = BeautifulSoup(body, 'html.parser').get_text()
        self.assertIn('Validation passed. AR: @Bob confirm release.', text)
        self.assertNotIn('Template hash:', text)
        self.assertNotIn('Evidence refs:', text)
        page.set_content(body)
        page.screenshot(path=str(directory / 'report-desktop.png'), full_page=True)
        self.assertEqual(3, page.locator('table thead th').count())
        self.assertEqual(2, page.locator('table tbody tr').count())
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(directory / 'report-phone.png'), full_page=True)
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        (directory / 'result.json').write_text(json.dumps({
            'status': 'passed', 'template_id': template_id, 'draft_id': draft.draft_id,
            'publication_id': publication_id, 'original_files_in_audit': 6,
            'real_provider_calls': 0, 'real_model_calls': 0,
        }, indent=2), encoding='utf-8')
