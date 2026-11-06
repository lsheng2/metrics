import json
from pathlib import Path

from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    ReportAuthoringBrowserTestCase,
    browser_page,
    fragment_text,
)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportAuthoringEditRuntimeBrowser(ReportAuthoringBrowserTestCase):
    def test_shouldReplaceSecondTokenWithRichInlineCandidateAndUndoOnceInNativeRuntime(self):
        draft = self.create_draft(770)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                async () => {
                    const { mount } = await import('/static/js/report_editor/adapter.js');
                    const host = document.createElement('section');
                    host.innerHTML = '<div id="runtime-token-region" data-region-id="runtime-token-region"></div>';
                    document.body.appendChild(host);
                    window.__providerCalls = 0;
                    window.__completionEvents = [];
                    window.__tokenOriginal = {
                        schema_version: 2,
                        blocks: [{
                            type: 'paragraph',
                            content: [{
                                type: 'text',
                                text: 'one #ALPHA-1 two #ALPHA-2 tail',
                                marks: [],
                                foreground: '#0055aa',
                                background: '#ffff00',
                            }],
                        }],
                    };
                    window.__tokenHandle = await mount(document.getElementById('runtime-token-region'), {
                        fragment: window.__tokenOriginal,
                        onCompletionToken: capture => window.__completionEvents.push(capture ? {
                            region_id: capture.region_id,
                            expected_text: capture.expected_text,
                            local_version: capture.local_version,
                        } : null),
                    });
                }
            """)
            page.locator('#runtime-token-region .ProseMirror').click()
            page.keyboard.press('End')
            for _ in range(5):
                page.keyboard.press('ArrowLeft')
            page.wait_for_function("window.__tokenHandle.captureToken()?.expected_text === '#ALPHA-2'")
            first = page.evaluate("""
                () => {
                    const candidate = {
                        schema_version: 2,
                        blocks: [{
                            type: 'paragraph',
                            content: [{
                                type: 'link',
                                href: 'https://tracker.example.test/browse/ALPHA-2',
                                content: [{
                                    type: 'text',
                                    text: 'ALPHA-2 linked',
                                    marks: ['strong'],
                                    foreground: null,
                                    background: null,
                                }],
                            }],
                        }],
                    };
                    const capture = window.__tokenHandle.captureToken();
                    const status = window.__tokenHandle.applyCandidate(capture, {fragment: candidate});
                    const duplicate = window.__tokenHandle.applyCandidate(capture, {text: 'duplicate'});
                    return {
                        status,
                        duplicate,
                        fragment: window.__tokenHandle.getFragment(),
                        events: window.__completionEvents,
                        providerCalls: window.__providerCalls,
                    };
                }
            """)
            page.keyboard.press('Control+Z')
            after_keyboard_undo = page.evaluate("window.__tokenHandle.getFragment()")
            page.keyboard.press('End')
            for _ in range(5):
                page.keyboard.press('ArrowLeft')
            page.wait_for_function("window.__tokenHandle.captureToken()?.expected_text === '#ALPHA-2'")
            second = page.evaluate("""
                async () => {
                    const capture = window.__tokenHandle.captureToken();
                    const invalid = window.__tokenHandle.applyCandidate(capture, {fragment: {
                        schema_version: 2,
                        blocks: [
                            {type: 'paragraph', content: [{type: 'text', text: 'first', marks: [], foreground: null, background: null}]},
                            {type: 'paragraph', content: [{type: 'text', text: 'second', marks: [], foreground: null, background: null}]},
                        ],
                    }});
                    const afterInvalid = window.__tokenHandle.getFragment();
                    const applied = window.__tokenHandle.applyCandidate(capture, {text: 'ALPHA-2 done'});
                    const afterApply = window.__tokenHandle.getFragment();
                    const commandUndo = window.__tokenHandle.command('undo');
                    const afterCommandUndo = window.__tokenHandle.getFragment();
                    const staleCapture = window.__tokenHandle.captureToken();
                    window.__tokenHandle.destroy();
                    const host = document.createElement('section');
                    host.innerHTML = '<div id="runtime-token-region-remount" data-region-id="runtime-token-region"></div>';
                    document.body.appendChild(host);
                    const { mount } = await import('/static/js/report_editor/adapter.js');
                    const remounted = await mount(document.getElementById('runtime-token-region-remount'), {
                        fragment: window.__tokenOriginal,
                    });
                    return {
                        invalid,
                        afterInvalid,
                        applied,
                        afterApply,
                        commandUndo,
                        afterCommandUndo,
                        remountStatus: remounted.applyCandidate(staleCapture, {text: 'late'}),
                    };
                }
            """)

        self.assertEqual('applied', first['status'])
        self.assertEqual('stale', first['duplicate'])
        self.assertEqual(0, first['providerCalls'])
        self.assertTrue(any(
            event and event['region_id'] == 'runtime-token-region' and event['expected_text'] == '#ALPHA-2'
            for event in first['events']
        ))
        self.assertEqual({
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [
                    self._text('one #ALPHA-1 two ', foreground='#0055aa', background='#ffff00'),
                    {
                        'type': 'link',
                        'href': 'https://tracker.example.test/browse/ALPHA-2',
                        'content': [self._text('ALPHA-2 linked', marks=['strong'], foreground='#0055aa', background='#ffff00')],
                    },
                    self._text(' tail', foreground='#0055aa', background='#ffff00'),
                ],
            }],
        }, first['fragment'])
        self.assertEqual({
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [self._text('one #ALPHA-1 two #ALPHA-2 tail', foreground='#0055aa', background='#ffff00')],
            }],
        }, after_keyboard_undo)
        self.assertEqual('stale', second['invalid'])
        self.assertEqual(after_keyboard_undo, second['afterInvalid'])
        self.assertEqual('applied', second['applied'])
        self.assertIn('ALPHA-2 done', fragment_text(second['afterApply']))
        self.assertTrue(second['commandUndo'])
        self.assertEqual(after_keyboard_undo, second['afterCommandUndo'])
        self.assertEqual('stale', second['remountStatus'])

    def test_shouldNotCaptureSyntheticTokenAcrossHardBreak(self):
        draft = self.create_draft(775)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                async () => {
                    const { mount } = await import('/static/js/report_editor/adapter.js');
                    const host = document.createElement('section');
                    host.innerHTML = '<div id="runtime-break-region" data-region-id="runtime-break-region"></div>';
                    document.body.appendChild(host);
                    window.__breakOriginal = {
                        schema_version: 2,
                        blocks: [{
                            type: 'paragraph',
                            content: [
                                {type: 'text', text: '#ALPHA-', marks: [], foreground: null, background: null},
                                {type: 'break'},
                                {type: 'text', text: '2', marks: [], foreground: null, background: null},
                            ],
                        }],
                    };
                    window.__breakHandle = await mount(document.getElementById('runtime-break-region'), {
                        fragment: window.__breakOriginal,
                    });
                }
            """)
            page.locator('#runtime-break-region .ProseMirror').click()
            point = page.evaluate("""
                () => {
                    const editor = document.querySelector('#runtime-break-region .ProseMirror');
                    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
                    let node = walker.nextNode();
                    while (node && node.textContent !== '2') {
                        node = walker.nextNode();
                    }
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    const rect = range.getBoundingClientRect();
                    return {x: rect.right + 2, y: rect.top + rect.height / 2};
                }
            """)
            page.mouse.click(point['x'], point['y'])
            result = page.evaluate("""
                () => {
                    const capture = window.__breakHandle.captureToken();
                    const status = window.__breakHandle.applyCandidate(capture, {text: 'ALPHA-2 linked'});
                    return {capture, status, fragment: window.__breakHandle.getFragment()};
                }
            """)

        self.assertIsNone(result['capture'])
        self.assertEqual('stale', result['status'])
        self.assertEqual({
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [
                    self._text('#ALPHA-'),
                    {'type': 'break'},
                    self._text('2'),
                ],
            }],
        }, result['fragment'])

    def test_shouldPreserveMixedForegroundWhenApplyingHighlightAcrossRunsAndLinks(self):
        draft = self.create_draft(780)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                async () => {
                    const { mount } = await import('/static/js/report_editor/adapter.js');
                    const host = document.createElement('section');
                    host.innerHTML = '<div id="runtime-paint-region" data-region-id="runtime-paint-region"></div>';
                    document.body.appendChild(host);
                    window.__paintHandle = await mount(document.getElementById('runtime-paint-region'), {
                        fragment: {
                            schema_version: 2,
                            blocks: [{
                                type: 'paragraph',
                                content: [
                                    {type: 'text', text: 'red ', marks: [], foreground: '#aa0000', background: null},
                                    {type: 'text', text: 'green ', marks: [], foreground: '#008000', background: null},
                                    {
                                        type: 'link',
                                        href: 'https://tracker.example.test/browse/LINK-1',
                                        content: [{type: 'text', text: 'link', marks: [], foreground: '#0055aa', background: null}],
                                    },
                                ],
                            }],
                        },
                    });
                }
            """)
            page.locator('#runtime-paint-region .ProseMirror').click()
            page.keyboard.press('Control+A')
            painted = page.evaluate("""
                () => {
                    const applied = window.__paintHandle.command('background', '#fff4cc');
                    return {applied, fragment: window.__paintHandle.getFragment()};
                }
            """)

        self.assertTrue(painted['applied'])
        self.assertEqual({
            'schema_version': 2,
            'blocks': [{
                'type': 'paragraph',
                'content': [
                    self._text('red ', foreground='#aa0000', background='#fff4cc'),
                    self._text('green ', foreground='#008000', background='#fff4cc'),
                    {
                        'type': 'link',
                        'href': 'https://tracker.example.test/browse/LINK-1',
                        'content': [self._text('link', foreground='#0055aa', background='#fff4cc')],
                    },
                ],
            }],
        }, painted['fragment'])

    def test_shouldSaveTaskTableCodeBlockAndBlockStyleWithoutSourceMode(self):
        draft = self.create_draft(790)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            self.assertEqual(0, page.locator('[data-report-source-mode], [data-report-source-toggle]').count())
            toolbar = page.locator('[data-report-shared-toolbar]')
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('Toolbar heading')
            page.keyboard.press('Control+A')
            toolbar.locator('select[data-report-command="block"]').select_option('h2')
            note.locator('.ProseMirror h2').wait_for()
            note.locator('.ProseMirror h2').click()
            page.keyboard.press('End')
            page.keyboard.press('Enter')
            toolbar.locator('select[data-report-command="code-block"]').select_option('json')
            note.locator('.ProseMirror pre code').wait_for(state='attached')
            page.keyboard.type('{"ok": true}')

            task = self._blank_note(page, 1)
            self._focus_region(task, page)
            page.keyboard.type('toggle me')
            page.keyboard.press('Control+A')
            toolbar.locator('[data-report-command="task"]').click()
            toolbar.locator('[data-report-command="task"]').click()
            task_item = task.locator('.ProseMirror li[data-item-type="task"]').first
            task_checked = task_item.get_attribute('data-checked')

            table = self._blank_note(page, 2)
            self._focus_region(table, page)
            toolbar.locator('[data-report-command="table"]').click()
            table.locator('.ProseMirror tbody td').first.click()
            toolbar.locator('[data-report-command="table-row-add"]').click()
            toolbar.locator('[data-report-command="table-column-add"]').click()
            table.locator('.ProseMirror tbody tr').nth(1).locator('td').nth(1).click()
            toolbar.locator('[data-report-command="table-row-delete"]').click()
            table.locator('.ProseMirror tbody tr').nth(1).locator('td').nth(1).click()
            toolbar.locator('[data-report-command="table-column-delete"]').click()
            table.locator('.ProseMirror tbody td').first.click()
            toolbar.locator('[data-report-command="table-row-add"]').click()
            toolbar.locator('[data-report-command="table-column-add"]').click()

            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as save_response:
                page.locator('[data-report-save-button]').click()
            save_status = save_response.value.status
            page.wait_for_load_state('domcontentloaded')
            payload = json.loads(page.locator('[name="authored_edits"]').input_value())

        blocks = [block for item in payload for block in item['fragment']['blocks']]
        self.assertEqual(200, save_status)
        self.assertEqual('true', task_checked)
        self.assertTrue(any(block['type'] == 'heading' and block['level'] == 2 and 'Toolbar heading' in fragment_text({'blocks': [block]}) for block in blocks), blocks)
        self.assertTrue(any(block['type'] == 'code' and block['language'] == 'json' and '{"ok": true}' in block['text'] for block in blocks), blocks)
        self.assertTrue(any(block['type'] == 'list' and block['items'][0]['checked'] is True for block in blocks), blocks)
        self.assertTrue(any(block['type'] == 'table' and len(block['headers']) == 2 and len(block['rows']) == 2 for block in blocks), blocks)

    def test_shouldApplyReferencePopupSaveReopenAndKeepErrorTextWithVisibleLocalIcons(self):
        draft = self.create_draft(795)
        screenshot = Path('.tmp/authoring-main-20261103/references-editor-ui.png').resolve()

        with browser_page(self.editor_url(draft.draft_id)) as page:
            metrics = page.evaluate("""
                () => {
                    const root = document.querySelector('[data-report-editor]');
                    const icons = Array.from(root.querySelectorAll('.report-editor-toolbar [class*="iconoir-"]'));
                    const row = root.querySelector('.report-row-editor');
                    const title = root.querySelector('.report-row-editor .title');
                    return {
                        icons: icons.map(icon => {
                            const style = getComputedStyle(icon);
                            const rect = icon.getBoundingClientRect();
                            return {width: rect.width, height: rect.height, mask: style.maskImage || style.webkitMaskImage};
                        }),
                        rowColor: getComputedStyle(row).color,
                        titleColor: getComputedStyle(title).color,
                    };
                }
            """)
            self.assertTrue(all(item['width'] >= 10 and item['height'] >= 10 and 'iconoir' in item['mask'] for item in metrics['icons']))
            self.assertEqual('rgb(17, 24, 39)', metrics['rowColor'])
            self.assertEqual('rgb(17, 24, 39)', metrics['titleColor'])

            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.keyboard.press('ArrowDown')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            page.wait_for_function("document.querySelector('.report-completion-menu') === null")
            applied = note.locator('.ProseMirror').text_content()
            page.keyboard.press('Control+Z')
            undone = note.locator('.ProseMirror').text_content()

            self._focus_region(note, page)
            page.keyboard.press('Control+A')
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.keyboard.press('ArrowDown')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            page.wait_for_function("document.querySelector('.report-completion-menu') === null")

            out_of_scope = self._blank_note(page, 1)
            self._focus_region(out_of_scope, page)
            page.keyboard.type('#BETA-9')
            page.locator('.report-completion-message').wait_for()
            page.keyboard.press('Enter')
            retained = out_of_scope.locator('.ProseMirror').text_content()
            page.screenshot(path=str(screenshot), full_page=True)

            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as save_response:
                page.locator('[data-report-save-button]').click()
            save_status = save_response.value.status
            page.wait_for_load_state('domcontentloaded')

        reopened = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        reference_edit = next(edit for edit in reopened.authored_edits if edit.reference_observations)
        self.assertIn('ALPHA-1 Browser linked title @Alice', applied)
        self.assertEqual('#ALPHA-1', undone)
        self.assertEqual('#BETA-9', retained)
        self.assertEqual(200, save_status)
        self.assertEqual(1, len(reference_edit.reference_observations))
        self.assertTrue(screenshot.exists())

    def _blank_note(self, page, index):
        return page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(index)

    def _focus_region(self, region, page):
        region.locator('[data-report-editor-surface]').click()
        region.locator('.ProseMirror').wait_for()
        region.locator('.ProseMirror').click()

    def _text(self, value, marks=None, foreground=None, background=None):
        return {
            'type': 'text',
            'text': value,
            'marks': marks or [],
            'foreground': foreground,
            'background': background,
        }
