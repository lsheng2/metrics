import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from django.test import override_settings

from project_management.app.api import reports as report_api
from project_management.app.domain.report_authoring_fragments import plain_text_fragment, rich_text_fragment_plain_text
from project_management.services.report_assist_receipts import ReportAssistReceiptVerifier
from project_management.tests.test_report_assist_service import make_assist_environment
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import fetch_local_route_response, fulfill_route_response
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page
from ui_web.views.report_assists import ReportAssistView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportAssistBrowser(ReportHistoryUiBrowserSupport):
    def test_shouldApplyDailyCandidateThenSaveItsProvenanceThroughMountedEditor(self):
        draft = self.prepared_continuity_draft()
        env = make_assist_environment(Path(self.temporary.name), draft_service=self.service, draft=draft)
        self.service.assist_verifier = ReportAssistReceiptVerifier(env.service.contract)
        evidence = Path('.tmp/dashboard-assist-20261106') / f'browser-{uuid4()}'
        evidence.mkdir(parents=True)
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                region = page.locator(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]')
                region.locator('[data-report-editor-surface]').click()
                region.locator('.ProseMirror').wait_for()
                page.locator('[data-report-assist-open]').click()
                page.locator('[data-report-assist-instruction]').fill('Summarize the current next action.')
                with page.expect_response(lambda response: response.url.endswith('/assists/')
                                          and response.request.method == 'POST') as pending:
                    page.locator('[data-report-assist-generate]').click()
                response = pending.value
                (evidence / 'submit.json').write_text(json.dumps({
                    'status': response.status, 'body': response.json(),
                }, indent=2), encoding='utf-8')
                self.assertEqual(200, response.status, response.text())
                page.locator('[data-report-assist-apply]').wait_for()
                self.assert_dialog_fits(page)
                page.screenshot(path=str(evidence / 'candidate.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                self.assert_dialog_fits(page)
                page.screenshot(path=str(evidence / 'candidate-phone.png'), full_page=True)
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.locator('[data-report-assist-apply]').click()
                self.assertIn('Review the validation result.', region.inner_text())
                self.assertEqual('true', page.locator('[data-report-editor]').get_attribute('data-report-authoring-dirty'))
                unsaved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
                self.assertEqual(draft.revision, unsaved.revision)
                with page.expect_response('**/save/') as saved_response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, saved_response.value.status, saved_response.value.text())
                page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
                region = page.locator(f'[data-continuity-current-note-id="{note_id}"]')
                region.scroll_into_view_if_needed()
                page.screenshot(path=str(evidence / 'saved.png'), full_page=True)
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        edit = next(edit for edit in saved.authored_edits if edit.target == {'scope': 'daily_note', 'note_id': note_id})
        note = next(note for note in saved.authoring_context['notes'] if note['note_id'] == note_id)
        self.assertEqual('ai_assisted', edit.origin)
        self.assertEqual(edit.source_ai_result_ref, note['provenance']['ai_result_ref'])
        self.assertEqual('ai_assisted', note['provenance']['origin'])
        self.assertEqual(1, len([item for item in env.requests if item[0] == 'POST']))

    def test_shouldRejectCandidateAfterNewHumanText(self):
        self.reject_stale_candidate('text')

    def test_shouldRejectCandidateAfterPaintOnlyChange(self):
        self.reject_stale_candidate('paint')

    def reject_stale_candidate(self, mutation):
        draft, env, note_id = self.assist_case()
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                region = self.daily_region(page, note_id)
                self.generate_candidate(page, region)
                region.locator('.ProseMirror').focus()
                page.keyboard.press('Control+End')
                if mutation == 'text':
                    page.keyboard.type(' Human follow-up.')
                else:
                    page.keyboard.press('Control+A')
                    page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
                self.assertTrue(page.locator('[data-report-assist-apply]').is_disabled())
                self.assertIn('target changed', page.locator('[data-report-assist-status]').inner_text())
                page.locator('[data-report-assist-cancel]').click()
                page.locator('[data-report-assist-dialog]').wait_for(state='hidden')
                self.assertNotIn('Review the validation result.', region.inner_text())
                self.assertEqual('true', page.locator('[data-report-editor]').get_attribute('data-report-authoring-dirty'))
        original = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        self.assertEqual(1, original.revision)
        self.assertEqual(1, len([item for item in env.requests if item[0] == 'POST']))

    def test_shouldUndoApplyAndSaveLaterHumanPaintWithoutForgedAiAttribution(self):
        draft, env, note_id = self.assist_case()
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                region = self.daily_region(page, note_id)
                before = region.locator('[data-report-editor-surface]').inner_text()
                self.generate_candidate(page, region)
                page.locator('[data-report-assist-apply]').click()
                page.locator('[data-report-command="undo"]').click()
                self.assertEqual(before, region.locator('.ProseMirror').inner_text())
                page.locator('[data-report-command="redo"]').click()
                self.assertIn('Review the validation result.', region.inner_text())
                region.locator('.ProseMirror').focus()
                page.keyboard.press('Control+A')
                page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
                with page.expect_response('**/save/') as saved_response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, saved_response.value.status, saved_response.value.text())
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        edit = next(item for item in saved.authored_edits if item.target == {'scope': 'daily_note', 'note_id': note_id})
        self.assertEqual('human', edit.origin)
        self.assertIsNone(edit.source_ai_result_ref)
        self.assertEqual('#0055aa', edit.fragment['blocks'][0]['content'][0]['foreground'])

    def test_shouldKeepManualEditingAvailableWhenAiIsUnavailableInChinese(self):
        draft, env, note_id = self.assist_case()
        env.service.backend = None
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id), language='zh-hans') as page:
                region = self.daily_region(page, note_id)
                region.locator('[data-report-editor-surface]').click()
                region.locator('.ProseMirror').wait_for()
                page.locator('[data-report-assist-open]').click()
                page.wait_for_function("document.querySelector('[data-report-assist-status]').textContent.includes('手工编辑')")
                self.assertTrue(page.locator('[data-report-assist-generate]').is_disabled())
                self.assert_dialog_fits(page)
                page.locator('[data-report-assist-close]').click()
                region.locator('.ProseMirror').click()
                page.keyboard.press('Control+A')
                page.keyboard.type('Manual note with AI unavailable.')
                with page.expect_response('**/save/') as saved_response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, saved_response.value.status, saved_response.value.text())
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        edit = next(item for item in saved.authored_edits if item.target == {'scope': 'daily_note', 'note_id': note_id})
        self.assertEqual('Manual note with AI unavailable.', rich_text_fragment_plain_text(edit.fragment))
        self.assertEqual([], env.requests)

    def test_shouldSaveAiAcceptanceEvenWhenCandidateMatchesExistingText(self):
        draft, env, note_id = self.assist_case()
        original = next(item for item in draft.authoring_context['notes'] if item['note_id'] == note_id)
        draft = self.service.save_authored(
            self.actor, self.project.id, self.stage.id, draft.draft_id,
            command_id=str(uuid4()), expected_revision=1, expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                str(uuid4()), 'note', {'scope': 'daily_note', 'note_id': note_id},
                plain_text_fragment('Review the validation result.'), original['body_hash'],
            ),),
        )
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                self.generate_candidate(page, self.daily_region(page, note_id))
                page.locator('[data-report-assist-apply]').click()
                self.assertEqual('true', page.locator('[data-report-editor]').get_attribute('data-report-authoring-dirty'))
                with page.expect_response('**/save/') as response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, response.value.status, response.value.text())
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        edit = next(item for item in saved.authored_edits if item.target == {'scope': 'daily_note', 'note_id': note_id})
        self.assertEqual('ai_assisted', edit.origin)

    def test_shouldReopenStoredCandidateWithoutAnotherGeneration(self):
        draft, env, note_id = self.assist_case()
        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                region = self.daily_region(page, note_id)
                self.generate_candidate(page, region)
                page.locator('[data-report-assist-close]').click()
                page.reload(wait_until='domcontentloaded')
                region.locator('[data-report-editor-surface]').click()
                region.locator('.ProseMirror').wait_for()
                page.locator('[data-report-assist-open]').click()
                page.locator('[data-report-assist-apply]').wait_for()
                page.locator('[data-report-assist-apply]').click()
                self.assertIn('Review the validation result.', region.inner_text())
        self.assertEqual(1, len([item for item in env.requests if item[0] == 'POST']))

    def test_shouldRetireAcceptedReceiptAndAdvanceNoteHashesWhileNewerLocalEditsRemain(self):
        draft, env, note_id = self.assist_case()
        held = {}

        def hold_save(route):
            held['response'] = fetch_local_route_response(route)
            held['route'] = route

        with patch.object(ReportAssistView, 'service_factory', staticmethod(lambda: env.service)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                self.generate_candidate(page, self.daily_region(page, note_id))
                page.locator('[data-report-assist-apply]').click()
                page.route('**/save/', hold_save)
                page.locator('[data-report-save-button]').click()
                page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringSaving === 'true'")
                other_id = draft.authoring_context['current_observations'][1]['note_id']
                other = self.daily_region(page, other_id)
                other.locator('[data-report-editor-surface]').click()
                other.locator('.ProseMirror').wait_for()
                other.locator('.ProseMirror').click()
                page.keyboard.press('Control+A')
                page.keyboard.type('Newer human note while AI acceptance saves.')
                self.assertIn('Newer human note while AI acceptance saves.', other.inner_text())
                self.assertEqual(200, held['response'].status, held['response'].body)
                fulfill_route_response(held['route'], held['response'])
                page.unroute('**/save/')
                page.wait_for_function("document.querySelector('[data-report-editor]').dataset.revision === '2'")
                with page.expect_response('**/save/') as response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, response.value.status, response.value.text())
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        ai_edit = next(item for item in saved.authored_edits if item.target == {'scope': 'daily_note', 'note_id': note_id})
        human_edit = next(item for item in saved.authored_edits if item.target == {'scope': 'daily_note', 'note_id': other_id})
        self.assertEqual(3, saved.revision)
        self.assertEqual('ai_assisted', ai_edit.origin)
        self.assertEqual('Newer human note while AI acceptance saves.', rich_text_fragment_plain_text(human_edit.fragment))

    def assist_case(self):
        draft = self.prepared_continuity_draft()
        env = make_assist_environment(Path(self.temporary.name), draft_service=self.service, draft=draft)
        self.service.assist_verifier = ReportAssistReceiptVerifier(env.service.contract)
        return draft, env, draft.authoring_context['current_observations'][0]['note_id']

    def daily_region(self, page, note_id):
        page.set_default_timeout(10000)
        return page.locator(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]')

    def generate_candidate(self, page, region):
        region.locator('[data-report-editor-surface]').click()
        region.locator('.ProseMirror').wait_for()
        page.locator('[data-report-assist-open]').click()
        page.locator('[data-report-assist-instruction]').fill('Summarize the current next action.')
        with page.expect_response(lambda response: response.url.endswith('/assists/')
                                  and response.request.method == 'POST') as pending:
            page.locator('[data-report-assist-generate]').click()
        self.assertEqual(200, pending.value.status, pending.value.text())
        page.locator('[data-report-assist-apply]').wait_for()

    def assert_dialog_fits(self, page):
        bounds = page.locator('[data-report-assist-dialog]').evaluate("""element => {
            const rect = element.getBoundingClientRect();
            const button = element.querySelector('[data-report-assist-cancel]');
            const action = button.getBoundingClientRect();
            const preview = element.querySelector('[data-report-assist-preview] p');
            const luminance = color => color.match(/\\d+/g).slice(0, 3)
                .map(value => Number(value) / 255)
                .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
                .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
            const foreground = preview ? luminance(getComputedStyle(preview).color) : null;
            const background = luminance(getComputedStyle(element).backgroundColor);
            const revision = document.querySelector('[data-report-editor] > .level code').getBoundingClientRect();
            return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                    width: innerWidth, height: innerHeight, scroll: element.scrollWidth,
                    client: element.clientWidth, revisionRight: revision.right,
                    contrast: foreground === null ? null : (Math.max(foreground, background) + 0.05)
                        / (Math.min(foreground, background) + 0.05),
                    actionVisible: button.contains(document.elementFromPoint(
                        action.left + action.width / 2, action.top + action.height / 2))};
        }""")
        self.assertGreaterEqual(bounds['left'], 0, bounds)
        self.assertGreaterEqual(bounds['top'], 0, bounds)
        self.assertLessEqual(bounds['right'], bounds['width'], bounds)
        self.assertLessEqual(bounds['bottom'], bounds['height'], bounds)
        self.assertLessEqual(bounds['scroll'], bounds['client'], bounds)
        self.assertLessEqual(bounds['revisionRight'], bounds['width'], bounds)
        self.assertTrue(bounds['actionVisible'], bounds)
        if bounds['contrast'] is not None:
            self.assertGreaterEqual(bounds['contrast'], 4.5, bounds)
