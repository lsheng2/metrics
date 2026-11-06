import re
import threading

from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    authored_text_from_fields,
    browser_page,
    fetch_local_route_response,
    form_fields_from_request,
    fragment_text,
    fulfill_route_response,
    ReportAuthoringBrowserTestCase,
)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportAuthoringLifecycleBrowser(ReportAuthoringBrowserTestCase):
    def test_shouldKeepLocalEditDirtyWhenDelayedAcceptedSaveReturnsAndThenSaveIt(self):
        draft = self.create_draft(720)
        save_fields = []
        clipboard_revisions = []

        def record_clipboard(route):
            clipboard_revisions.append(route.request.url.rsplit('revision=', 1)[-1])
            route.continue_()

        def delay_first_save(route):
            save_fields.append(form_fields_from_request(route.request))
            route.continue_()

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                () => {
                    const originalFetch = window.fetch.bind(window);
                    window.__saveResponseReady = false;
                    window.__releaseSaveResponse = null;
                    window.fetch = async (...args) => {
                        const response = await originalFetch(...args);
                        const url = String(args[0]);
                        if (!url.endsWith('/save/')) {
                            return response;
                        }
                        window.__saveResponseReady = true;
                        return await new Promise(resolve => {
                            window.__releaseSaveResponse = () => resolve(response);
                        });
                    };
                }
            """)
            page.route(re.compile(r'.*/clipboard/\?revision=.*'), record_clipboard)
            page.route('**/save/', delay_first_save)
            editor = self._blank_note(page, 0)
            self._type_in_editor(editor, page, 'accepted A')
            first_command = page.locator('[data-report-authored-form] [name="command_id"]').input_value()
            page.locator('[data-report-save-button]').click()
            page.wait_for_function('window.__saveResponseReady === true')
            editor.locator('.ProseMirror').click()
            page.keyboard.type(' local B')
            page.evaluate('window.__releaseSaveResponse()')
            self._wait_for_save_idle(page)
            first_response_state = self._authoring_state(page)
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as second_response:
                page.locator('[data-report-save-button]').click()
            second_status = second_response.value.status
            page.wait_for_load_state('domcontentloaded')

        revision_two = self.service.render(self.actor, self.project.id, self.stage.id, draft.draft_id, revision=2)
        revision_three = self.service.render(self.actor, self.project.id, self.stage.id, draft.draft_id, revision=3)
        self.assertEqual(200, second_status)
        self.assertEqual(2, len(save_fields))
        self.assertEqual(first_command, save_fields[0]['command_id'])
        self.assertNotEqual(save_fields[0]['command_id'], save_fields[1]['command_id'])
        self.assertIn('accepted A', authored_text_from_fields(save_fields[0]))
        self.assertNotIn('local B', authored_text_from_fields(save_fields[0]))
        self.assertIn('accepted A local B', authored_text_from_fields(save_fields[1]))
        self.assertEqual('true', first_response_state['dirty'])
        self.assertEqual('false', first_response_state['saving'])
        self.assertEqual('2', first_response_state['expectedRevision'])
        self.assertNotEqual(first_command, first_response_state['commandId'])
        self.assertEqual('2', first_response_state['rootRevision'])
        self.assertIn('revision=2', first_response_state['clipboardUrl'])
        self.assertEqual('2', first_response_state['finalizeExpectedRevision'])
        self.assertTrue(first_response_state['copyDisabled'])
        self.assertTrue(first_response_state['finalizeDisabled'])
        self.assertIn('accepted A local B', first_response_state['editorText'])
        self.assertIn('2', clipboard_revisions)
        self.assertIn('accepted A', revision_two.plain_text)
        self.assertNotIn('local B', revision_two.plain_text)
        self.assertIn('accepted A local B', revision_three.plain_text)

    def test_shouldRetryUncertainAcceptedSaveWithOriginalBodyAndKeepNewLocalEditDirty(self):
        draft = self.create_draft(730)
        first_accepted = threading.Event()
        save_fields = []

        def lose_first_response(route):
            save_fields.append(form_fields_from_request(route.request))
            response = fetch_local_route_response(route)
            if len(save_fields) == 1:
                first_accepted.set()
                route.abort()
                return
            fulfill_route_response(route, response)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/save/', lose_first_response)
            editor = self._blank_note(page, 0)
            self._type_in_editor(editor, page, 'retry A')
            page.locator('[data-report-save-button]').click()
            self.assertTrue(first_accepted.wait(10))
            self._wait_for_save_idle(page)
            editor.locator('.ProseMirror').click()
            page.keyboard.type(' local B')
            page.locator('[data-report-save-button]').click()
            page.wait_for_function("document.querySelector('[name=\"expected_revision\"]').value === '2'")
            retry_state = self._authoring_state(page)
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as third_response:
                page.locator('[data-report-save-button]').click()
            third_status = third_response.value.status
            page.wait_for_load_state('domcontentloaded')

        revision_two = self.service.render(self.actor, self.project.id, self.stage.id, draft.draft_id, revision=2)
        revision_three = self.service.render(self.actor, self.project.id, self.stage.id, draft.draft_id, revision=3)
        self.assertEqual(200, third_status)
        self.assertEqual(3, len(save_fields))
        self.assertEqual(save_fields[0]['command_id'], save_fields[1]['command_id'])
        self.assertEqual(save_fields[0]['expected_revision'], save_fields[1]['expected_revision'])
        self.assertEqual(save_fields[0]['expected_revision_hash'], save_fields[1]['expected_revision_hash'])
        self.assertEqual(save_fields[0]['authored_edits'], save_fields[1]['authored_edits'])
        self.assertNotEqual(save_fields[1]['command_id'], save_fields[2]['command_id'])
        self.assertIn('retry A', authored_text_from_fields(save_fields[1]))
        self.assertNotIn('local B', authored_text_from_fields(save_fields[1]))
        self.assertIn('retry A local B', authored_text_from_fields(save_fields[2]))
        self.assertEqual('true', retry_state['dirty'])
        self.assertEqual('false', retry_state['saving'])
        self.assertEqual('false', retry_state['uncertain'])
        self.assertEqual('2', retry_state['expectedRevision'])
        self.assertIn('retry A local B', retry_state['editorText'])
        self.assertIn('retry A', revision_two.plain_text)
        self.assertNotIn('local B', revision_two.plain_text)
        self.assertIn('retry A local B', revision_three.plain_text)

    def test_shouldDestroyLateMountAndAvoidOldSubmitHandlersAfterRemount(self):
        draft = self.create_draft(740)
        save_fields = []

        def record_save(route):
            save_fields.append(form_fields_from_request(route.request))
            fulfill_route_response(route, fetch_local_route_response(route))

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                () => {
                    const original = window.ReportMilkdownEditor.createRuntime;
                    window.__mountControl = {started: 0, destroyed: 0, release: null, original};
                    window.ReportMilkdownEditor.createRuntime = async (...args) => {
                        window.__mountControl.started += 1;
                        await new Promise(resolve => { window.__mountControl.release = resolve; });
                        const runtime = await original(...args);
                        const originalDestroy = runtime.destroy ? runtime.destroy.bind(runtime) : null;
                        runtime.destroy = () => {
                            window.__mountControl.destroyed += 1;
                            if (originalDestroy) originalDestroy();
                        };
                        return runtime;
                    };
                }
            """)
            self._blank_note(page, 0).locator('[data-report-editor-surface]').click()
            page.wait_for_function('window.__mountControl.started === 1')
            page.evaluate("document.querySelector('[data-report-editor]').__reportAuthoring.destroy()")
            page.evaluate('window.__mountControl.release()')
            page.wait_for_function('window.__mountControl.destroyed === 1')
            page.evaluate("""
                async () => {
                    window.ReportMilkdownEditor.createRuntime = window.__mountControl.original;
                    const module = await import('/static/js/report_editor/index.js');
                    module.initializeReportAuthoring(document.querySelector('[data-report-editor]'));
                }
            """)
            page.route('**/save/', record_save)
            remounted = self._blank_note(page, 0)
            self._type_in_editor(remounted, page, 'after remount')
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/save/')) as response:
                page.locator('[data-report-save-button]').click()
            status = response.value.status
            page.wait_for_load_state('domcontentloaded')

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        self.assertEqual(200, status)
        self.assertEqual(1, len(save_fields))
        self.assertIn('after remount', fragment_text(saved.authored_edits[0].fragment))

    def test_shouldClearDirtyAfterUndoAndKeepTextWhenExitIsCanceled(self):
        draft = self.create_draft(750)

        with browser_page(self.editor_url(draft.draft_id)) as page:
            editor = self._blank_note(page, 0)
            self._type_in_editor(editor, page, 'x')
            page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty === 'true'")
            page.locator('[data-report-command="undo"]').click()
            after_undo = self._authoring_state(page)
            self.assertEqual('false', after_undo['dirty'], after_undo)
            page.keyboard.press('ArrowLeft')
            selection_state = self._authoring_state(page)
            page.keyboard.type('kept after cancel')
            blocked = page.evaluate("""
                () => {
                    window.__confirmText = null;
                    window.confirm = text => { window.__confirmText = text; return false; };
                    const link = document.querySelector('nav.breadcrumb a[href]');
                    const event = new MouseEvent('click', {bubbles: true, cancelable: true});
                    link.dispatchEvent(event);
                    const editor = document.querySelector('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"] .ProseMirror');
                    return {
                        blocked: event.defaultPrevented,
                        confirmText: window.__confirmText,
                        text: editor.textContent,
                        dirty: document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty,
                    };
                }
            """)

        self.assertEqual('false', selection_state['dirty'])
        self.assertTrue(blocked['blocked'])
        self.assertIn('Unsaved', blocked['confirmText'])
        self.assertIn('kept after cancel', blocked['text'])
        self.assertEqual('true', blocked['dirty'])

    def test_shouldLetCentralGuardOwnDirtyLanguageSwitchDiscardDecision(self):
        draft = self.create_draft(760)
        save_requests = []
        language_requests = []
        dialogs = []

        def record_save(route):
            save_requests.append(form_fields_from_request(route.request))
            fulfill_route_response(route, fetch_local_route_response(route))

        def record_language(route):
            language_requests.append(form_fields_from_request(route.request))
            route.continue_()

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.route('**/save/', record_save)
            page.route('**/projects/language/', record_language)
            page.on('dialog', lambda dialog: (dialogs.append(dialog.type), dialog.accept()))
            editor = self._blank_note(page, 0)
            self._type_in_editor(editor, page, 'language dirty')
            page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty === 'true'")
            page.locator('form[action*="projects/language"] select[name="language"]').select_option('zh-hans')
            canceled = page.evaluate("""
                () => {
                    let confirms = 0;
                    window.confirm = () => { confirms += 1; return false; };
                    const form = document.querySelector('form[action*="projects/language"]');
                    const event = new SubmitEvent('submit', {bubbles: true, cancelable: true, submitter: form.querySelector('button')});
                    form.dispatchEvent(event);
                    return {
                        prevented: event.defaultPrevented,
                        confirms,
                        text: document.querySelector('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"] .ProseMirror').textContent,
                    };
                }
            """)
            page.evaluate("window.confirm = () => true")
            with page.expect_response(lambda response: response.request.method == 'POST' and '/projects/language/' in response.url) as language_response:
                page.locator('form[action*="projects/language"] button[type="submit"]').click()
            status = language_response.value.status
            page.wait_for_load_state('domcontentloaded')

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        self.assertTrue(canceled['prevented'])
        self.assertEqual(1, canceled['confirms'])
        self.assertIn('language dirty', canceled['text'])
        self.assertEqual(302, status)
        self.assertEqual(1, len(language_requests))
        self.assertEqual('zh-hans', language_requests[0]['language'])
        self.assertEqual([], save_requests)
        self.assertEqual([], dialogs)
        self.assertEqual(1, saved.revision)
        self.assertEqual((), saved.authored_edits)

    def _blank_note(self, page, index):
        return page.locator('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"]').nth(index)

    def _type_in_editor(self, region, page, text):
        region.locator('[data-report-editor-surface]').click()
        region.locator('.ProseMirror').wait_for()
        region.locator('.ProseMirror').click()
        page.keyboard.type(text)

    def _wait_for_save_idle(self, page):
        page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringSaving === 'false'")

    def _authoring_state(self, page):
        return page.evaluate("""
            () => {
                const root = document.querySelector('[data-report-editor]');
                const editor = document.querySelector('[data-report-wysiwyg-region][data-existing="false"][data-edit-kind="note"] .ProseMirror');
                const finalizeExpected = document.querySelector('.dashboard-action-form [name="expected_revision"]');
                return {
                    dirty: root.dataset.reportAuthoringDirty,
                    saving: root.dataset.reportAuthoringSaving,
                    uncertain: root.dataset.reportAuthoringUncertain,
                    failed: root.dataset.reportAuthoringFailed,
                    rootRevision: root.dataset.revision,
                    rootRevisionHash: root.dataset.revisionHash,
                    clipboardUrl: root.dataset.clipboardUrl,
                    expectedRevision: document.querySelector('[data-report-authored-form] [name="expected_revision"]').value,
                    expectedRevisionHash: document.querySelector('[data-report-authored-form] [name="expected_revision_hash"]').value,
                    commandId: document.querySelector('[data-report-authored-form] [name="command_id"]').value,
                    finalizeExpectedRevision: finalizeExpected ? finalizeExpected.value : null,
                    copyDisabled: document.querySelector('[data-report-copy-button]').disabled,
                    finalizeDisabled: document.querySelector('[data-report-finalize-button]').disabled,
                    editorText: editor ? editor.textContent : '',
                };
            }
        """)
