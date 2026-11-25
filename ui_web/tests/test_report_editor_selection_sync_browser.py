from contextlib import contextmanager

from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    ReportAuthoringBrowserTestCase,
    browser_page,
)


@override_settings(
    METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
    METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
    WHITENOISE_AUTOREFRESH=True,
)
class TestReportEditorSelectionSyncBrowser(ReportAuthoringBrowserTestCase):
    def test_shouldKeepHeadingWhenNativeCaretPrecedesSelectionChange(self):
        with self.runtime_page() as page:
            result = page.evaluate("""() => {
                const heading = document.querySelector('#selection-owner h2');
                const before = window.selectionRuntime.selectionLocation();
                window.getSelection().collapse(heading.firstChild, heading.textContent.length);
                const applied = window.selectionRuntime.command('code-block', 'json');
                return {before, applied, fragment: window.selectionRuntime.getFragment()};
            }""")

        self.assertEqual({'from': 0, 'to': 17}, result['before'])
        self.assertTrue(result['applied'])
        self.assertEqual([
            self.heading('Toolbar heading'),
            {'type': 'code', 'language': 'json', 'text': ''},
        ], result['fragment']['blocks'])

    def test_shouldKeepIntentionalWholeDocumentSelection(self):
        with self.runtime_page() as page:
            result = page.evaluate("""() => {
                const applied = window.selectionRuntime.command('code-block', 'json');
                return {applied, fragment: window.selectionRuntime.getFragment()};
            }""")

        self.assertTrue(result['applied'])
        self.assertEqual([
            {'type': 'code', 'language': 'json', 'text': 'Toolbar heading'},
        ], result['fragment']['blocks'])

    def test_shouldIgnoreSelectionOutsideTheOwningEditor(self):
        with self.runtime_page() as page:
            result = page.evaluate("""() => {
                const elsewhere = document.createElement('p');
                elsewhere.textContent = 'Other selection';
                document.body.appendChild(elsewhere);
                window.getSelection().collapse(elsewhere.firstChild, 5);
                const applied = window.selectionRuntime.command('code-block', 'json');
                return {applied, fragment: window.selectionRuntime.getFragment(),
                    elsewhere: elsewhere.textContent};
            }""")

        self.assertTrue(result['applied'])
        self.assertEqual('Other selection', result['elsewhere'])
        self.assertEqual([
            {'type': 'code', 'language': 'json', 'text': 'Toolbar heading'},
        ], result['fragment']['blocks'])

    def test_shouldUseNativeRangeWithoutConvertingAnotherBlock(self):
        blocks = [self.heading('First heading'), self.heading('Second heading')]
        with self.runtime_page(blocks) as page:
            result = page.evaluate("""() => {
                const second = document.querySelectorAll('#selection-owner h2')[1];
                const range = document.createRange();
                range.selectNodeContents(second.firstChild);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                const applied = window.selectionRuntime.command('code-block', 'json');
                return {applied, fragment: window.selectionRuntime.getFragment()};
            }""")

        self.assertTrue(result['applied'])
        self.assertEqual([
            self.heading('First heading'),
            {'type': 'code', 'language': 'json', 'text': 'Second heading'},
        ], result['fragment']['blocks'])

    @contextmanager
    def runtime_page(self, blocks=None):
        draft = self.create_draft(799)
        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""async blocks => {
                const owner = document.createElement('section');
                owner.id = 'selection-owner';
                owner.dataset.regionId = 'selection-owner';
                document.body.appendChild(owner);
                window.selectionRuntime = await window.ReportMilkdownEditor.createRuntime(
                    owner, {schema_version: 2, blocks});
            }""", blocks or [self.heading('Toolbar heading')])
            page.locator('#selection-owner .ProseMirror').click()
            page.keyboard.press('Control+A')
            yield page

    @staticmethod
    def heading(text):
        return {'type': 'heading', 'level': 2, 'content': [
            {'type': 'text', 'text': text, 'marks': [], 'foreground': None, 'background': None},
        ]}
