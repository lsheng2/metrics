import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings

from project_management.app.api import reports as report_api
from project_management.tests.report_user_workflow_fixtures import source_for
from project_management.tests.test_report_standup import standup_document
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page
from ui_web.views.report_recovery import ReportRecoveryView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportUserWorkflowBrowser(ReportHistoryUiBrowserSupport):
    def test_unsaved_note_action_and_review_recover_after_browser_restart_then_save(self):
        self.source.snapshot = source_for()
        setup = self.continuity_setup(23000, document=standup_document())
        draft = self.prepared_continuity_draft(setup=setup, command_index=23002)
        args = self.actor, self.project.id, self.stage.id, draft.draft_id
        recovery = report_api.ReportRecoveryService(self.service)
        directory = Path('.tmp/dashboard-user-workflow-20261107') / f'browser-{uuid4()}'
        directory.mkdir(parents=True)
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        selector = f'[data-continuity-current-note-id="{note_id}"]'
        with patch.object(ReportRecoveryView, 'service_factory', staticmethod(lambda: recovery)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                page.set_default_timeout(15000)
                page.locator(selector + ' [data-report-editor-surface]').click()
                editor = page.locator(selector + ' .ProseMirror')
                editor.wait_for()
                editor.fill('Human note survives browser restart.')
                editor.press('Control+A')
                page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
                page.locator('[data-continuity-add-action]').click()
                action = page.locator('[data-new-report-action]')
                action.locator('input').fill('Bob')
                action.locator('.ProseMirror').wait_for()
                action.locator('.ProseMirror').fill('Validate the next build.')
                page.locator('[data-continuity-add-persistent][data-persistent-target="report"]').click()
                page.locator('[data-continuity-persistent-draft] .ProseMirror').wait_for()
                page.locator('[data-continuity-persistent-draft] .ProseMirror').fill('Retain this meeting context.')
                with page.expect_response(lambda response: '/recovery/' in response.url
                                          and response.request.method == 'POST'
                                          and 'set_meeting_review' in (response.request.post_data or '')
                                          and 'Validate the next build.' in (response.request.post_data or '')) as checkpoint:
                    page.locator('[data-meeting-review]').select_option('discussed')
                self.assertEqual(200, checkpoint.value.status, checkpoint.value.text())
                page.wait_for_function("Boolean(document.querySelector('[data-report-editor]').dataset.recoverySequence)")
                self.assertEqual('1', page.locator('[data-report-editor]').get_attribute('data-revision'))
                page.screenshot(path=str(directory / 'unsaved-checkpoint.png'), full_page=True)
            self.assertEqual(1, self.service.get(*args).revision)
            self.assertEqual(1, len(recovery.list(*args)))
            with project_page(self.editor_url(draft.draft_id), language='zh-hans') as page:
                page.set_default_timeout(15000)
                page.locator('[data-recovery-restore]:not([disabled])').wait_for()
                self.assertNotIn('Human note survives browser restart.', page.locator(selector).inner_text())
                page.locator('[data-recovery-restore]').click()
                page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty === 'true'")
                self.assertIn('Human note survives browser restart.', page.locator(selector).inner_text())
                action = page.locator('[data-new-report-action]')
                self.assertEqual('Bob', action.locator('input').input_value())
                action.locator('.ProseMirror').wait_for()
                self.assertEqual('Validate the next build.', action.locator('.ProseMirror').inner_text())
                self.assertEqual('Retain this meeting context.', page.locator('[data-continuity-persistent-draft] .ProseMirror').inner_text())
                self.assertEqual('discussed', page.locator('[data-meeting-review]').input_value())
                page.locator('[data-new-report-action]').scroll_into_view_if_needed()
                page.screenshot(path=str(directory / 'restored-zh-desktop.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                page.locator('[data-new-report-action]').scroll_into_view_if_needed()
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(directory / 'restored-zh-mobile.png'), full_page=True)
                with page.expect_response('**/save/') as response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, response.value.status, response.value.text())
                page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
                page.screenshot(path=str(directory / 'saved-zh-mobile.png'), full_page=True)
                details = page.locator('[data-continuity-action-control]').first
                details.locator('summary').click()
                details.locator('[data-report-action-owner]').fill('Carol')
                details.locator('[data-report-action-state]').select_option('done')
                details.locator('[data-continuity-action-editor]').click()
                details.locator('[data-continuity-action-editor] .ProseMirror').wait_for()
                details.locator('[data-continuity-action-editor] .ProseMirror').fill('Validated during meeting.')
                with page.expect_response('**/save/') as response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, response.value.status, response.value.text())
                page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '3'")
                details = page.locator('[data-continuity-action-control]').first
                details.locator('summary').click()
                self.assertEqual('done', details.locator('[data-report-action-state]').input_value())
                details.locator('[data-report-action-state]').select_option('open')
                with page.expect_response('**/save/') as response:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, response.value.status, response.value.text())
                page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '4'")
                page.locator('[data-continuity-action-control]').first.scroll_into_view_if_needed()
                page.locator('[data-continuity-action-control] summary').first.click()
                page.screenshot(path=str(directory / 'reopened-ar-zh-mobile.png'), full_page=True)
            saved = self.service.get(*args)
            self.assertEqual(4, saved.revision)
            self.assertEqual('#0055aa', saved.authoring_context['notes'][0]['body_fragment']['blocks'][0]['content'][0]['foreground'])
            self.assertEqual('Carol', saved.authoring_context['actions'][0]['owner_ref']['display_name'])
            self.assertEqual('open', saved.authoring_context['actions'][0]['tracking_state'])
            self.assertEqual('discussed', saved.authoring_context['meeting_reviews'][0]['state'])
            self.assertEqual('Retain this meeting context.', saved.authoring_context['persistent_notes'][0]['fragment']['blocks'][0]['content'][0]['text'])
            self.assertEqual((), recovery.list(*args))
            (directory / 'result.json').write_text(json.dumps({
                'status': 'passed', 'draft_id': draft.draft_id, 'revision': saved.revision,
                'browser_restart': True, 'human_action_count': len(saved.authoring_context['actions']),
                'real_provider_calls': 0, 'real_model_calls': 0,
            }, indent=2), encoding='utf-8')

    def test_lost_save_response_keeps_checkpoint_downloadable_without_replaying_over_advanced_revision(self):
        self.source.snapshot = source_for()
        setup = self.continuity_setup(23200, document=standup_document())
        draft = self.prepared_continuity_draft(setup=setup, command_index=23202)
        args = self.actor, self.project.id, self.stage.id, draft.draft_id
        recovery = report_api.ReportRecoveryService(self.service)
        with patch.object(ReportRecoveryView, 'service_factory', staticmethod(lambda: recovery)):
            with project_page(self.editor_url(draft.draft_id)) as page:
                page.set_default_timeout(15000)
                page.locator('[data-continuity-current-note-id] [data-report-editor-surface]').click()
                page.locator('[data-continuity-current-note-id] .ProseMirror').fill('Server saved but reply lost.')
                submitted = []

                def lose_save_reply(route):
                    submitted.append(route.request.post_data)
                    response = route.fetch()
                    self.assertEqual(200, response.status, response.text())
                    route.abort()

                page.route('**/save/', lose_save_reply)
                with page.expect_response(lambda response: '/recovery/' in response.url
                                          and response.request.method == 'POST'
                                          and '"save_request":{' in (response.request.post_data or '')) as checkpoint:
                    page.locator('[data-report-save-button]').click()
                self.assertEqual(200, checkpoint.value.status, checkpoint.value.text())
                self.assertFalse(checkpoint.value.json()['result']['restorable'])
                self.assertEqual(1, len(submitted))
                self.assertEqual(2, self.service.get(*args).revision)
            with project_page(self.editor_url(draft.draft_id)) as page:
                page.set_default_timeout(15000)
                page.locator('[data-recovery-download]:not([disabled])').wait_for()
                self.assertTrue(page.locator('[data-recovery-restore]').is_disabled())
                with page.expect_download() as pending:
                    page.locator('[data-recovery-download]').click()
                artifact = json.loads(Path(pending.value.path()).read_text(encoding='utf-8'))
                self.assertIsNotNone(artifact['content']['save_request'])
                self.assertFalse(artifact['restorable'])
                with page.expect_response(lambda response: '/recovery/' in response.url and response.request.method == 'POST') as deleted:
                    page.locator('[data-recovery-discard]').click()
                self.assertEqual(200, deleted.value.status, deleted.value.text())
            self.assertEqual(2, self.service.get(*args).revision)
            self.assertEqual((), recovery.list(*args))
