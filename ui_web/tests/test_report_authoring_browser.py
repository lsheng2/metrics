import json

from django.test import override_settings

from project_management.app.api import reports as report_api
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.report_render_fixtures import source_key_hash
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    ReportAuthoringBrowserTestCase,
    browser_page,
    fragment_text,
)
from ui_web.tests.test_report_authoring_views import fragment


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportAuthoringBrowser(ReportAuthoringBrowserTestCase):
    def test_shouldRenderSafeRichFragmentsBeforeFocusAndBlockDirtyNavigation(self):
        draft = self.create_draft(700)
        token = 'safe-script-token'
        saved = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(701),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '10000000-0000-4000-8000-000000000701',
                'note',
                {'scope': 'report'},
                {
                    'schema_version': 2,
                    'blocks': [{
                        'type': 'paragraph',
                        'content': [{
                            'type': 'link',
                            'href': 'https://tracker.example.test/browse/ALPHA-1',
                            'content': [{
                                'type': 'text',
                                'text': f'{token}</script><script>window.__editorCanary=1</script>',
                                'marks': ['strong'],
                                'foreground': '#0055aa',
                                'background': '#fff4cc',
                            }],
                        }],
                    }],
                },
            ),),
            continuity_changes=(),
        )

        with browser_page(self.editor_url(saved.draft_id)) as page:
            result = page.evaluate("""
                token => {
                    const region = Array.from(document.querySelectorAll('[data-report-wysiwyg-region][data-existing="true"]'))
                        .find(item => item.textContent.includes(token));
                    const link = region.querySelector('.report-fragment-preview a');
                    const span = link.querySelector('span');
                    return {
                        canary: window.__editorCanary || null,
                        executableCanaryCount: Array.from(document.scripts).filter(
                            item => item.textContent.includes('window.__editorCanary=1') && item.type !== 'application/json'
                        ).length,
                        hasEditorBeforeFocus: Boolean(region.querySelector('.ProseMirror')),
                        text: span.textContent,
                        color: getComputedStyle(span).color,
                        background: getComputedStyle(span).backgroundColor,
                        href: link.href,
                    };
                }
            """, token)
            first_blank_note = page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(0)
            first_blank_note.locator('[data-report-editor-surface]').click()
            first_blank_note.locator('.ProseMirror').wait_for()
            first_blank_note.locator('.ProseMirror').click()
            page.keyboard.type('dirty browser guard')
            blocked = page.evaluate("""
                () => {
                    window.__confirmText = null;
                    window.confirm = text => { window.__confirmText = text; return false; };
                    const link = document.querySelector('nav.breadcrumb a[href]');
                    const event = new MouseEvent('click', {bubbles: true, cancelable: true});
                    link.dispatchEvent(event);
                    return {blocked: event.defaultPrevented, confirmText: window.__confirmText};
                }
            """)

        self.assertEqual(saved.revision, 2)
        self.assertIsNone(result['canary'])
        self.assertEqual(0, result['executableCanaryCount'])
        self.assertFalse(result['hasEditorBeforeFocus'])
        self.assertIn(token, result['text'])
        self.assertEqual('rgb(0, 85, 170)', result['color'])
        self.assertEqual('rgb(255, 244, 204)', result['background'])
        self.assertEqual('https://tracker.example.test/browse/ALPHA-1', result['href'])
        self.assertTrue(blocked['blocked'])
        self.assertIn('Unsaved', blocked['confirmText'])

    def test_shouldPasteAllBlocksKeepActionOverrideAndRecoverFromStaleSave(self):
        draft = self.create_draft(710)
        row = draft.snapshot.rows[0]
        action_target = {
            'scope': 'action',
            'source_key_hash': source_key_hash(row.source_key),
            'summary_id': row.summary_ref.summary_id,
            'action_index': 0,
            'field': 'owner_display',
        }
        prepared = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(711),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '20000000-0000-4000-8000-000000000711',
                'narrative_override',
                action_target,
                fragment('Browser owner override'),
                expected_original_hash=report_api.text_hash(row.next_actions[0]['owner_id']),
            ),),
            continuity_changes=(),
        )

        with browser_page(self.editor_url(draft.draft_id)) as page:
            target = page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(0)
            target.locator('[data-report-editor-surface]').click()
            target.locator('.ProseMirror').wait_for()
            target.locator('.ProseMirror').click()
            page.evaluate("""
                () => new Promise(resolve => {
                    const target = document.querySelector('.ProseMirror');
                    const data = new DataTransfer();
                    data.setData('text/html', '<p>first pasted block</p><p>second pasted block</p>');
                    target.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData: data}));
                    setTimeout(resolve, 250);
                })
            """)
            toolbar = page.locator('[data-report-shared-toolbar]')
            task_region = page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(1)
            task_region.locator('[data-report-editor-surface]').click()
            task_region.locator('.ProseMirror').wait_for()
            task_region.locator('.ProseMirror').click()
            page.keyboard.type('toggle me')
            page.keyboard.press('Control+A')
            toolbar.locator('[data-report-command="task"]').click()
            toolbar.locator('[data-report-command="task"]').click()
            table_region = page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(2)
            table_region.locator('[data-report-editor-surface]').click()
            table_region.locator('.ProseMirror').wait_for()
            table_region.locator('.ProseMirror').click()
            toolbar.locator('[data-report-command="table"]').click()
            toolbar.locator('[data-report-command="table-row-add"]').click()
            toolbar.locator('[data-report-command="table-column-add"]').click()
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as save_response:
                page.locator('[data-report-save-button]').click()
            save_status = save_response.value.status
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_selector('[data-report-wysiwyg-region][data-existing="true"]')
            payload = json.loads(page.locator('[name="authored_edits"]').input_value())
            retained = [item for item in payload if item['edit_id'] == '20000000-0000-4000-8000-000000000711']
            pasted_text = '\n'.join(fragment_text(item['fragment']) for item in payload)
            task_fragments = [item['fragment'] for item in payload if 'toggle me' in fragment_text(item['fragment'])]
            tables = [block for item in payload for block in item['fragment']['blocks'] if block.get('type') == 'table']

            stale = page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(0)
            stale.locator('[data-report-editor-surface]').click()
            stale.locator('.ProseMirror').wait_for()
            stale.locator('.ProseMirror').click()
            page.keyboard.type('dirty after stale')
            page.evaluate("""
                () => {
                    document.querySelector('[name="expected_revision"]').value = '1';
                    document.querySelector('[name="expected_revision_hash"]').value = '0'.repeat(64);
                }
            """)
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as stale_response:
                page.locator('[data-report-save-button]').click()
            stale_status = stale_response.value.status
            stale_state = page.evaluate("""
                () => ({
                    dirty: document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty,
                    text: document.querySelector('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"] .ProseMirror').textContent,
                })
            """)

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        self.assertEqual(200, save_status)
        self.assertEqual(409, stale_status)
        self.assertEqual('true', stale_state['dirty'])
        self.assertIn('dirty after stale', stale_state['text'])
        self.assertEqual(1, len(retained))
        self.assertIn('first pasted block', pasted_text)
        self.assertIn('second pasted block', pasted_text)
        self.assertTrue(any(item['items'][0]['checked'] is True for fragment in task_fragments for item in fragment['blocks'] if item['type'] == 'list'))
        self.assertTrue(any(len(table['headers']) >= 2 and len(table['rows']) >= 2 for table in tables))
        self.assertIn('20000000-0000-4000-8000-000000000711', {edit.edit_id for edit in saved.authored_edits})
