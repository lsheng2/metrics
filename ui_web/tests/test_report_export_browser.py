import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from openpyxl import load_workbook

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page
from ui_web.views.report_exports import ReportDraftExportView, ReportPublicationExportView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportExportBrowser(ReportHistoryUiBrowserSupport):
    def setUp(self):
        super().setUp()
        for cls in (ReportDraftExportView, ReportPublicationExportView):
            patcher = patch.object(cls, 'facade_factory', staticmethod(self.report_facade))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_shouldDownloadSavedFormatsAndCopyRichHtmlThroughMountedControls(self):
        draft = self.prepared_continuity_draft()
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        evidence = Path('.tmp/dashboard-exports-20261106') / f'browser-{uuid4()}'
        evidence.mkdir(parents=True)
        marker = 'Export sample human note and AR follow-up.'
        href = 'https://tracker.example.test/review/DEMO-101'
        with project_page(self.editor_url(draft.draft_id)) as page:
            page.set_default_timeout(10000)
            page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
            controls = page.locator('[data-report-exports]')
            controls.wait_for()
            region = page.locator(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]')
            region.locator('[data-report-editor-surface]').click()
            region.locator('.ProseMirror').wait_for()
            region.locator('.ProseMirror').click()
            page.keyboard.press('Control+A')
            page.keyboard.type(marker)
            page.keyboard.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
            page.once('dialog', lambda dialog: dialog.accept(href))
            page.locator('[data-report-command="link"]').click()
            self.assertIsNone(controls.locator('[data-report-export-link]').get_attribute('href'))
            with page.expect_response('**/save/') as saved_response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, saved_response.value.status, saved_response.value.text())
            page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
            controls = page.locator('[data-report-exports]')
            page.wait_for_function("document.querySelector('[data-report-export-link]')?.href.includes('revision=2')")
            for format_name in ('markdown', 'xlsx'):
                controls.locator('[data-report-export-format]').select_option(format_name)
                with page.expect_download() as pending:
                    controls.locator('[data-report-export-link]').click()
                path = evidence / ('draft.md' if format_name == 'markdown' else 'draft.xlsx')
                pending.value.save_as(path)
            self.assertIn(marker, (evidence / 'draft.md').read_text(encoding='utf-8'))
            self.assertIn(href, (evidence / 'draft.md').read_text(encoding='utf-8'))
            workbook = load_workbook(evidence / 'draft.xlsx')
            self.assertTrue(any(marker in str(cell.value) for sheet in workbook for row in sheet for cell in row))
            page.locator('[data-report-copy-button]').click()
            page.wait_for_function("""() => {
                const root = document.querySelector('[data-report-editor]');
                return root.querySelector('[data-report-copy-status]').textContent === root.dataset.messageCopied;
            }""")
            clipboard = page.evaluate("""async () => {
                const items = await navigator.clipboard.read();
                const item = items.find(value => value.types.includes('text/html'));
                return {plain: await navigator.clipboard.readText(),
                        html: item ? await (await item.getType('text/html')).text() : ''};
            }""")
            self.assertTrue(marker in clipboard['plain'], 'Copied text did not contain the owned sample marker.')
            self.assertTrue(marker in clipboard['html'], 'Copied HTML did not contain the owned sample marker.')
            self.assertTrue('#aa0000' in clipboard['html'].lower() or 'rgb(170, 0, 0)' in clipboard['html'],
                            'Copied HTML did not preserve the sample paint.')
            (evidence / 'clipboard.html').write_text(clipboard['html'], encoding='utf-8')
            (evidence / 'clipboard.txt').write_text(clipboard['plain'], encoding='utf-8')
            page.screenshot(path=str(evidence / 'saved-desktop.png'), full_page=True)
            page.locator('[data-report-finalize-confirm]').check()
            with page.expect_navigation():
                page.locator('[data-report-finalize-button]').click()
            page.locator('[data-report-exports]').wait_for()
            with page.expect_download() as pending:
                page.locator('[data-report-export-link]').click()
            pending.value.save_as(evidence / 'publication.md')
            self.assertIn(marker, (evidence / 'publication.md').read_text(encoding='utf-8'))
            (evidence / 'result.json').write_text(json.dumps({
                'status': 'passed', 'draft_id': draft.draft_id, 'draft_revision': 2,
                'publication_url': page.url, 'browser_clipboard': 'html+plain',
                'outlook_qualified': False,
            }, indent=2), encoding='utf-8')

    def test_shouldFitChineseExportControlsOnPhoneWithoutChangingCanonicalLanguage(self):
        draft = self.prepared_continuity_draft()
        with project_page(self.editor_url(draft.draft_id), language='zh-hans') as page:
            page.set_default_timeout(10000)
            page.set_viewport_size({'width': 390, 'height': 844})
            controls = page.locator('[data-report-exports]')
            controls.wait_for()
            self.assertIn('导出', controls.inner_text())
            controls.locator('[data-report-export-format]').select_option('xlsx')
            bounds = controls.evaluate("""element => {
                const rect = element.getBoundingClientRect();
                return {left: rect.left, right: rect.right, width: innerWidth,
                        scroll: element.scrollWidth, client: element.clientWidth};
            }""")
            self.assertGreaterEqual(bounds['left'], 0, bounds)
            self.assertLessEqual(bounds['right'], bounds['width'], bounds)
            self.assertLessEqual(bounds['scroll'], bounds['client'], bounds)
            evidence = Path('.tmp/dashboard-exports-20261106') / f'phone-{uuid4()}.png'
            page.screenshot(path=str(evidence), full_page=True)
            with page.expect_download() as pending:
                page.locator('[data-report-export-link]').click()
            output = evidence.with_suffix('.xlsx')
            pending.value.save_as(output)
            workbook = load_workbook(output)
            self.assertIn('Report text', workbook.sheetnames)
