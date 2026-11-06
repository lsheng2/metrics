from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestContinuityToolbarBrowser(ReportHistoryUiBrowserSupport):
    def test_shouldApplySharedToolbarOnlyToTheLastFocusedEditor(self):
        draft = self.prepared_continuity_draft()
        with project_page(self.editor_url(draft.draft_id)) as page:
            region = page.locator('[data-continuity-current-note-id] [data-report-wysiwyg-region]').first
            region.locator('[data-report-editor-surface]').click()
            editor = region.locator('.ProseMirror')
            editor.wait_for()
            editor.fill('Regular note stays blue.')
            editor.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            page.locator('[data-continuity-add-persistent][data-persistent-target="report"]').click()
            persistent = page.locator('[data-continuity-persistent-draft] .ProseMirror')
            persistent.wait_for()
            persistent.fill('New persistent note stays green.')
            persistent.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#008000"]').click()
            self.assertEqual('rgb(0, 85, 170)', editor.locator('[style*="color"]').first.evaluate(
                'node => getComputedStyle(node).color'))
            editor.click()
            editor.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
            self.assertEqual('rgb(0, 128, 0)', persistent.locator('[style*="color"]').first.evaluate(
                'node => getComputedStyle(node).color'))
