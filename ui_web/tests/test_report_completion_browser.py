import json
from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    browser_page,
    fetch_local_route_response,
    form_fields_from_request,
    fulfill_route_response,
    ReportAuthoringBrowserTestCase,
)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportCompletionBrowser(ReportAuthoringBrowserTestCase):
    def test_shouldAnchorCompletionMenuToTokenAndNotRequeryAfterEscapeFocus(self):
        draft = self.create_draft(810)
        requests = []

        def record_completion(route):
            requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            install_geometry_helper(page)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('Context line one')
            page.keyboard.press('Enter')
            page.keyboard.type('Context line two')
            page.keyboard.press('Enter')
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            before = page.evaluate("completionGeometry()")
            page.keyboard.press('Escape')
            page.locator('.report-completion-menu').wait_for(state='detached')
            note.locator('.ProseMirror').click()
            page.wait_for_timeout(400)
            after_count = len(requests)

        self.assertLess(abs(before['menuLeft'] - before['tokenLeft']), 48, before)
        self.assertLessEqual(before['menuTop'], before['viewportBottom'] - before['menuHeight'])
        self.assertGreaterEqual(before['menuTop'], 0)
        self.assertNotEqual(round(before['menuTop']), round(before['regionBottom']), before)
        self.assertEqual(1, after_count)

    def test_shouldIgnoreLateResponseFromPreviousRegionAndApplyCurrentRegionOnly(self):
        draft = self.create_draft(811)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                () => {
                    const originalFetch = window.fetch.bind(window);
                    window.__heldCompletion = null;
                    window.__completionFetchCount = 0;
                    window.fetch = async (...args) => {
                        const url = String(args[0]);
                        if (!url.endsWith('/completions/')) {
                            return await originalFetch(...args);
                        }
                        window.__completionFetchCount += 1;
                        const holdThis = window.__completionFetchCount === 1;
                        const response = await originalFetch(...args);
                        if (holdThis) {
                            window.__firstResponseReady = true;
                            return await new Promise(resolve => {
                                window.__heldCompletion = () => resolve(response);
                            });
                        }
                        return response;
                    };
                }
            """)
            first = self._blank_note(page, 0)
            second = self._blank_note(page, 1)
            self._focus_region(first, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-message').wait_for()
            page.wait_for_function("window.__completionFetchCount === 1 && typeof window.__heldCompletion === 'function'")
            self._focus_region(second, page)
            page.keyboard.type('#ALPHA-1')
            page.wait_for_function("window.__completionFetchCount === 2")
            page.locator('.report-completion-option').first.wait_for()
            page.evaluate("window.__heldCompletion()")
            page.wait_for_timeout(200)
            page.keyboard.press('ArrowDown')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            first_text = first.locator('.ProseMirror').text_content()
            second_text = second.locator('.ProseMirror').text_content()

        self.assertEqual('#ALPHA-1', first_text)
        self.assertIn('ALPHA-1', second_text)
        self.assertIn('Browser linked title', second_text)

    def test_shouldNotApplyOrNavigateMenuDuringImeComposition(self):
        draft = self.create_draft(812)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            before = page.locator('.report-completion-option[aria-selected="true"]').text_content()
            page.evaluate("""
                () => document.querySelector('[data-report-editor]').dispatchEvent(
                    new CompositionEvent('compositionstart', {bubbles: true})
                )
            """)
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            page.wait_for_timeout(150)
            during = page.locator('.report-completion-option[aria-selected="true"]').text_content()
            text = note.locator('.ProseMirror').text_content()
            page.evaluate("""
                () => document.querySelector('[data-report-editor]').dispatchEvent(
                    new CompositionEvent('compositionend', {bubbles: true})
                )
            """)

        self.assertEqual(before, during)
        self.assertEqual('#ALPHA-1', text)

    def test_shouldDestroyCompletionListenersOnAuthoringTeardown(self):
        draft = self.create_draft(813)
        completion_requests = []

        def record_completion(route):
            completion_requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            first = self._blank_note(page, 0)
            self._focus_region(first, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.evaluate("document.querySelector('[data-report-editor]').__reportAuthoring.destroy()")
            page.evaluate("""
                async () => {
                    const module = await import('/static/js/report_editor/index.js');
                    module.initializeReportAuthoring(document.querySelector('[data-report-editor]'));
                }
            """)
            page.locator('.report-completion-menu').wait_for(state='detached')
            second = self._blank_note(page, 1)
            self._focus_region(second, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.keyboard.press('ArrowDown')
            page.keyboard.press('ArrowDown')
            page.keyboard.press('Enter')
            text = second.locator('.ProseMirror').text_content()

        self.assertEqual(2, len(completion_requests))
        self.assertIn('Browser linked title', text)

    def test_shouldConvertExpiredReferenceToOrdinaryHumanLinkWithoutLookup(self):
        draft = self.create_draft(814)
        save_posts = []
        completion_requests = []

        def record_completion(route):
            completion_requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        def expire_first_save(route):
            save_posts.append(form_fields_from_request(route.request))
            if len(save_posts) == 1:
                route.fulfill(status=409, content_type='application/json', body=json.dumps({
                    'state': 'failed',
                    'error_code': 'REFERENCE_RECEIPT_EXPIRED',
                    'message': 'expired',
                    'submitted_edits': json.loads(save_posts[0]['authored_edits']),
                }).encode('utf-8'))
                return
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            page.route('**/save/', expire_first_save)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.locator('.report-completion-option').nth(1).click()
            page.wait_for_function("""
                () => document.querySelector('[data-report-wysiwyg-region][data-existing="false"] .ProseMirror')
                    ?.textContent.includes('Browser linked title')
            """)
            page.locator('[data-report-save-button]').click()
            page.locator('[data-report-keep-human-link]').wait_for()
            page.locator('[data-report-keep-human-link]').click()
            before_second_save_requests = len(completion_requests)
            page.locator('[data-report-save-button]').click()
            page.wait_for_load_state('domcontentloaded')

        second_payload = json.loads(save_posts[1]['authored_edits'])
        links = [
            inline
            for edit in second_payload
            for block in edit['fragment']['blocks']
            for inline in block.get('content', [])
            if inline.get('type') == 'link'
        ]
        self.assertTrue(links, second_payload)
        link = links[0]
        self.assertEqual('link', link['type'])
        self.assertNotIn('reference_id', link)
        self.assertEqual([], second_payload[0]['reference_receipts'])
        self.assertEqual(before_second_save_requests, len(completion_requests))

    def test_shouldDismissEscapedTokenAcrossSelectionMovementUntilInputChanges(self):
        draft = self.create_draft(815)
        requests = []

        def record_completion(route):
            requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('A #ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.keyboard.press('Escape')
            page.keyboard.press('ArrowLeft')
            page.keyboard.press('ArrowRight')
            page.wait_for_timeout(400)
            after_revisit = len(requests)
            page.keyboard.press('Backspace')
            page.keyboard.type('1')
            page.locator('.report-completion-option').first.wait_for()
            after_input = len(requests)

        self.assertEqual(1, after_revisit)
        self.assertGreater(after_input, after_revisit)

    def test_shouldRejectBadOptionEnvelopeAndShowLocalizedErrorWithoutApplying(self):
        draft = self.create_draft(816)
        self.client.cookies['django_language'] = 'zh-hans'

        def bad_options(route):
            route.fulfill(status=200, content_type='application/json', body=json.dumps({
                'request_id': json.loads(route.request.post_data)['request_id'],
                'editor_epoch': json.loads(route.request.post_data)['editor_epoch'],
                'local_version': json.loads(route.request.post_data)['local_version'],
                'snapshot_hash': json.loads(route.request.post_data)['snapshot_hash'],
                'status': 'ready',
                'observed_at': '2026-11-03T01:00:00+00:00',
                'error': None,
                'options': [{'option_id': 'id_title', 'enabled': True, 'disabled_reason': None, 'fragment': {'schema_version': 2, 'blocks': []}, 'receipt': 'x'}],
            }).encode('utf-8'))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.context.add_cookies([{'name': 'django_language', 'value': 'zh-hans', 'url': self.live_server_url}])
            page.reload(wait_until='domcontentloaded')
            page.wait_for_selector('[data-report-wysiwyg-region]')
            page.route('**/completions/', bad_options)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-message').wait_for()
            page.wait_for_function("!document.querySelector('.report-completion-message')?.textContent.includes('Checking')")
            text = page.locator('.report-completion-message').text_content()
            page.keyboard.press('Enter')
            note_text = note.locator('.ProseMirror').text_content()

        self.assertIn('引用', text)
        self.assertEqual('#ALPHA-1', note_text)

    def test_shouldShowTooLongErrorWithoutCompletionRequest(self):
        draft = self.create_draft(817)
        requests = []

        def record_completion(route):
            requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-' + '1' * 40)
            page.locator('.report-completion-message').wait_for()
            message = page.locator('.report-completion-message').text_content()

        self.assertEqual([], requests)
        self.assertIn('31', message)

    def test_shouldAbortStaleClientRequestWhenTypingNewToken(self):
        draft = self.create_draft(818)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                () => {
                    const originalFetch = window.fetch.bind(window);
                    window.__abortSeen = false;
                    window.fetch = async (...args) => {
                        const init = args[1] || {};
                        if (String(args[0]).endsWith('/completions/')) {
                            init.signal?.addEventListener('abort', () => { window.__abortSeen = true; });
                            if (!window.__firstCompletionHeld) {
                                window.__firstCompletionHeld = true;
                                return await new Promise(() => {});
                            }
                        }
                        return await originalFetch(...args);
                    };
                }
            """)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-message').wait_for()
            page.wait_for_function('window.__firstCompletionHeld === true')
            page.keyboard.press('Control+A')
            page.keyboard.type('#ALPHA-2')
            page.wait_for_function('window.__abortSeen === true')

        self.assertTrue(True)

    def test_shouldNotQueryWhenCaretMovesOntoAnotherExistingToken(self):
        draft = self.create_draft(819)
        requests = []

        def record_completion(route):
            requests.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/completions/', record_completion)
            note = self._blank_note(page, 0)
            self._focus_region(note, page)
            page.keyboard.type('#ALPHA-1 before #ALPHA-1')
            page.locator('.report-completion-option').first.wait_for()
            page.keyboard.press('Escape')
            after_input = len(requests)
            click_token_occurrence(page, '#ALPHA-1', 0)
            page.wait_for_timeout(400)
            after_selection = len(requests)

        self.assertEqual(after_input, after_selection)

    def _blank_note(self, page, index):
        return page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(index)

    def _focus_region(self, region, page):
        region.locator('[data-report-editor-surface]').click()
        region.locator('.ProseMirror').wait_for()
        region.locator('.ProseMirror').click()


def install_geometry_helper(page):
    page.evaluate("""
        () => {
            window.completionGeometry = () => {
                const editor = document.querySelector('[data-report-wysiwyg-region][data-existing="false"] .ProseMirror');
                const menu = document.querySelector('.report-completion-menu');
                const region = document.querySelector('[data-report-wysiwyg-region][data-existing="false"]');
                const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
                let node = walker.nextNode();
                while (node && !node.textContent.includes('#ALPHA-1')) node = walker.nextNode();
                const range = document.createRange();
                range.setStart(node, node.textContent.indexOf('#ALPHA-1'));
                range.setEnd(node, node.textContent.indexOf('#ALPHA-1') + '#ALPHA-1'.length);
                const token = range.getBoundingClientRect();
                const menuRect = menu.getBoundingClientRect();
                const regionRect = region.getBoundingClientRect();
                return {
                    tokenLeft: token.left,
                    tokenTop: token.top,
                    tokenBottom: token.bottom,
                    menuLeft: menuRect.left,
                    menuTop: menuRect.top,
                    menuHeight: menuRect.height,
                    regionBottom: regionRect.bottom,
                    viewportBottom: window.innerHeight,
                };
            };
        }
    """)


def click_token_occurrence(page, token, occurrence):
    point = page.evaluate("""
        ([token, occurrence]) => {
            const editor = document.querySelector('[data-report-wysiwyg-region][data-existing="false"] .ProseMirror');
            const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
            let node = walker.nextNode();
            let seen = 0;
            while (node) {
                let start = node.textContent.indexOf(token);
                while (start >= 0) {
                    if (seen === occurrence) {
                        const range = document.createRange();
                        range.setStart(node, start + token.length);
                        range.setEnd(node, start + token.length);
                        const rect = range.getBoundingClientRect();
                        return {x: rect.left, y: rect.top + rect.height / 2};
                    }
                    seen += 1;
                    start = node.textContent.indexOf(token, start + token.length);
                }
                node = walker.nextNode();
            }
            throw new Error('token not found');
        }
    """, [token, occurrence])
    page.mouse.click(point['x'], point['y'])
