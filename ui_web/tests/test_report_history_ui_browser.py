import json
from urllib.parse import quote
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.report_draft_fixtures import draft_command
from ui_web.report_authoring_forms import ReportAuthoredSaveForm
from ui_web.report_template_documents import continuity_starter_document
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    fetch_local_route_response,
    form_fields_from_request,
    fulfill_route_response,
)
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page


SCREENSHOT_DIR = '.tmp/authoring-main-20261103'
COLORED_MATRIX_REOPEN_SCREENSHOT = SCREENSHOT_DIR + '/history-ui-colored-matrix-reopen.png'


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportHistoryUiBrowser(ReportHistoryUiBrowserSupport):
    def template_library_url(self):
        return self.live_server_url + reverse('ui_web:report_templates', kwargs={
            'project_id': self.project.id,
        })

    def stage_reports_url(self):
        return self.live_server_url + reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def test_shouldCreateContinuityTemplateThenCreateSeriesThroughActualUi(self):
        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy continuity daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            first_source = page.locator('[data-template-row]').first.locator('[data-template-data-source]').input_value()
            schema_version = page.evaluate("""
                () => JSON.parse(document.querySelector('[data-template-document-field]').value).schema_version
            """)
            daily_instruction_visible = page.locator('[data-template-daily-note-instructions]').is_visible()
            page.locator('[data-template-daily-note-instructions]').fill('Keep today concise.')
            with page.expect_navigation():
                page.locator('[data-template-save-button]').click()

        ready = self.template_service.list(self.actor, self.project.id, limit=20, offset=0).items[0]
        with project_page(self.stage_reports_url()) as page:
            initial_series_rows = page.locator('[data-report-series-row]').count()
            series_form = page.locator('[data-report-series-form]')
            series_form.locator('[name="series_name"]').fill('Current day continuity')
            series_form.locator('[name="template_choice"]').select_option(
                f'user|{ready.template_id}|{ready.current_revision}|{ready.revision_hash}'
            )
            with page.expect_navigation():
                page.locator('[data-report-series-create]').click()
            series_rows = page.locator('[data-report-series-row]').count()
            series_text = page.locator('[data-report-series-row]').first.text_content()

        series = self.continuity_service.list_series(self.actor, self.project.id, self.stage.id).items[0]
        template = self.template_service.get(self.actor, self.project.id, str(ready.template_id), revision=ready.current_revision)
        matrix = next(block for block in template.document['blocks'] if block['source'] == 'meeting_matrix')

        self.assertEqual('meeting_matrix', first_source)
        self.assertEqual(2, schema_version)
        self.assertEqual('none', matrix['options']['group_mode'])
        self.assertEqual([], matrix['options']['groups'])
        self.assertTrue(daily_instruction_visible)
        self.assertEqual(0, initial_series_rows)
        self.assertEqual(1, series_rows)
        self.assertIn('Current day continuity', series_text)
        self.assertEqual(series.default_template_selection.template_id, str(ready.template_id))
        self.assertEqual('Keep today concise.', template.fill_policy['daily_note_instructions'])

    def test_shouldBuildManualMatrixGroupsAndMoveRowByGroupSelector(self):
        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy continuity daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            matrix_row = page.locator('[data-template-row]').first
            matrix_row.locator('[data-template-matrix-group-add]').click()
            matrix_row.locator('[data-template-matrix-group-label]').last.fill('Frontend')
            matrix_row.locator('[data-template-matrix-group-add]').click()
            matrix_row.locator('[data-template-matrix-group-label]').last.fill('Backend')
            matrix_row.locator('[data-template-matrix-group-command="up"]').last.click()
            with page.expect_navigation():
                page.locator('[data-template-save-button]').click()

        ready = self.template_service.list(self.actor, self.project.id, limit=20, offset=0).items[0]
        template = self.template_service.get(self.actor, self.project.id, str(ready.template_id), revision=ready.current_revision)
        matrix = next(block for block in template.document['blocks'] if block['source'] == 'meeting_matrix')
        groups = matrix['options']['groups']
        template_selection = report_api.UserTemplateSelection(str(ready.template_id), ready.current_revision, ready.revision_hash)
        series = self.continuity_service.create_series(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(7720),
            name='Grouped series',
            calendar=report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}),
            template_selection=template_selection,
        )
        draft = self.prepared_continuity_draft(setup={'template_selection': template_selection, 'series': series}, command_index=7721)
        target_group = groups[1]['group_id']
        save_errors = []

        with project_page(self.editor_url(draft.draft_id)) as page:
            page.wait_for_selector('[data-continuity-row-group]')
            page.locator('[data-continuity-row-group]').first.select_option(target_group)
            def record_save(route):
                response = fetch_local_route_response(route)
                save_errors.append(response.body.decode('utf-8', errors='replace'))
                fulfill_route_response(route, response)
            page.route('**/save/', record_save)
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, response.value.status, {
                'body': save_errors[-1] if save_errors else '',
                'continuity_changes': form_fields_from_request(response.value.request).get('continuity_changes'),
            })

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)

        self.assertEqual('manual', matrix['options']['group_mode'])
        self.assertEqual(['Backend', 'Frontend'], [group['label'] for group in groups])
        self.assertEqual([0, 1], [group['rank'] for group in groups])
        self.assertEqual(len({group['group_id'] for group in groups}), 2)
        self.assertEqual(target_group, saved.authoring_context['row_order']['rows'][0]['group_id'])

    def test_shouldKeepSeriesPolicyInputWhenStaleSaveIsRejected(self):
        setup = self.continuity_setup(7600)
        series = setup['series']
        self.continuity_service.save_series_policy(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(7602),
            series_id=series.series_id,
            expected_revision=series.revision,
            expected_revision_hash=series.revision_hash,
            name='Server-side newer name',
            calendar=series.calendar,
            template_selection=series.default_template_selection,
        )
        url = reverse('ui_web:report_series_policy', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'series_id': series.series_id,
        })
        choice = (
            f'user|{series.default_template_selection.template_id}|'
            f'{series.default_template_selection.revision}|'
            f'{series.default_template_selection.revision_hash}'
        )
        response = self.client.post(url, {
            'command_id': draft_command(7603),
            'expected_revision': str(series.revision),
            'expected_revision_hash': series.revision_hash,
            'series_name': 'Unsaved stale UI name',
            'calendar_choice': 'iso8601',
            'timezone': 'Asia/Shanghai',
            'template_choice': choice,
        }, **self.auth('alice'))
        body = response.content.decode('utf-8')

        self.assertEqual(409, response.status_code)
        self.assertIn('Unsaved stale UI name', body)
        self.assertIn('Series policy has changed', body)

    def test_shouldRenderFixedTemplateContentAsRichReadonlyHtml(self):
        document = continuity_starter_document('daily')
        fixed = {
            'kind': 'content',
            'block_id': '21000000-0000-4000-8000-000000000001',
            'fragment': {
                'schema_version': 2,
                'blocks': [{
                    'type': 'paragraph',
                    'content': [{
                        'type': 'link',
                        'href': 'https://tracker.example.test/fixed',
                        'content': [{
                            'type': 'text',
                            'text': 'Fixed rich link',
                            'marks': ['strong'],
                            'foreground': '#0055aa',
                            'background': '#fff4cc',
                        }],
                    }],
                }],
            },
        }
        setup = self.continuity_setup(7650, document={**document, 'blocks': (fixed, *document['blocks'])})
        draft = self.prepared_continuity_draft(setup=setup, command_index=7652)

        with project_page(self.live_server_url + reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        })) as page:
            page.wait_for_selector('[data-template-fixed-content] a[href="https://tracker.example.test/fixed"]')
            observed = page.evaluate("""
                () => {
                    const link = document.querySelector('[data-template-fixed-content] a');
                    const text = Array.from(link.querySelectorAll('*')).find(node => node.textContent.includes('Fixed rich link'));
                    return {
                        href: link.href,
                        text: link.textContent,
                        color: getComputedStyle(text).color,
                        background: getComputedStyle(text).backgroundColor,
                        weight: getComputedStyle(text).fontWeight,
                    };
                }
            """)

        self.assertEqual('https://tracker.example.test/fixed', observed['href'].rstrip('/'))
        self.assertIn('Fixed rich link', observed['text'])
        self.assertEqual('rgb(0, 85, 170)', observed['color'])
        self.assertEqual('rgb(255, 244, 204)', observed['background'])
        self.assertIn(observed['weight'], {'700', 'bold'})

    def test_shouldSaveColoredCurrentMatrixNoteWithExpectedOriginalHashThroughActualEditor(self):
        draft = self.prepared_continuity_draft()
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        original_hash = next(note for note in draft.authoring_context['notes'] if note['note_id'] == note_id)['body_hash']
        requests = []

        def record_save(route):
            requests.append(form_fields_from_request(route.request))
            response = fetch_local_route_response(route)
            requests[-1]['__status'] = response.status
            requests[-1]['__body'] = response.body.decode('utf-8', errors='replace')
            fulfill_route_response(route, response)

        with project_page(self.live_server_url + reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        })) as page:
            content = page.content()
            self.assertIn('data-continuity-matrix', content)
            self.assertIn(note_id, content)
            page.wait_for_selector(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]')
            region = page.locator(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]').first
            region.locator('[data-report-editor-surface]').click()
            region.locator('.ProseMirror').wait_for()
            region.locator('.ProseMirror').click()
            page.keyboard.press('Control+A')
            page.keyboard.type('B2 blue current note')
            page.keyboard.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            page.route('**/save/', record_save)
            with page.expect_response('**/save/') as save_response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, save_response.value.status, requests[0]['__body'])
            page.wait_for_selector(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region][data-existing="true"]')
            reopened = page.evaluate("""
                noteId => {
                    const root = document.querySelector(`[data-continuity-current-note-id="${noteId}"]`);
                    const region = root.querySelector('[data-report-wysiwyg-region]');
                    const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number).map(v => {
                        v /= 255;
                        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                    });
                    const opaqueBackground = node => {
                        let current = node;
                        while (current) {
                            const color = getComputedStyle(current).backgroundColor;
                            if (color && color !== 'rgba(0, 0, 0, 0)' && !color.endsWith(', 0)')) return color;
                            current = current.parentElement;
                        }
                        throw new Error('no opaque background');
                    };
                    const contrast = (node) => {
                        if (!node) throw new Error('missing contrast node');
                        const style = getComputedStyle(node);
                        const fg = rgb(style.color);
                        const bg = rgb(opaqueBackground(node));
                        const fl = 0.2126 * fg[0] + 0.7152 * fg[1] + 0.0722 * fg[2];
                        const bl = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2];
                        return (Math.max(fl, bl) + 0.05) / (Math.min(fl, bl) + 0.05);
                    };
                    const ticket = document.querySelector('[data-matrix-ticket-key]');
                    const prefix = document.querySelector('[data-matrix-source-prefix]');
                    const action = document.querySelector('[data-matrix-action-label]');
                    const actionBody = document.querySelector('[data-matrix-action-body]');
                    const readonlyText = document.querySelector('[data-matrix-readonly-note]');
                    return {
                        text: root.textContent,
                        existing: region.dataset.existing,
                        readonlyCopies: document.querySelectorAll('[data-matrix-readonly-note]').length,
                        ticketContrast: contrast(ticket),
                        prefixText: prefix.textContent,
                        prefixContrast: contrast(prefix),
                        actionContrast: contrast(action),
                        actionBodyContrast: contrast(actionBody),
                        actionBodyVisible: Boolean(actionBody.offsetParent),
                        actionBodyText: actionBody.textContent,
                        readonlyContrast: readonlyText ? contrast(readonlyText) : 7,
                        actionText: action ? action.textContent : '',
                    };
                }
            """, note_id)
            screenshot_path = f'{SCREENSHOT_DIR}/history-ui-colored-matrix-contrast-{uuid4()}.png'
            page.screenshot(path=screenshot_path, full_page=True)

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        note = next(note for note in saved.authoring_context['notes'] if note['note_id'] == note_id)
        edits = json.loads(requests[0]['authored_edits'])

        self.assertEqual(1, len(requests))
        self.assertEqual('[]', requests[0]['continuity_changes'])
        self.assertIn('B2 blue current note', reopened['text'])
        self.assertEqual('true', reopened['existing'])
        self.assertEqual(0, reopened['readonlyCopies'])
        self.assertEqual('ww45.1(In Progress):', reopened['prefixText'])
        self.assertGreaterEqual(reopened['ticketContrast'], 4.5)
        self.assertGreaterEqual(reopened['prefixContrast'], 4.5)
        self.assertGreaterEqual(reopened['actionContrast'], 4.5)
        self.assertGreaterEqual(reopened['actionBodyContrast'], 4.5)
        self.assertTrue(reopened['actionBodyVisible'])
        self.assertIn('Retest fixed patch', reopened['actionBodyText'])
        self.assertGreaterEqual(reopened['readonlyContrast'], 4.5)
        self.assertIn('AR', reopened['actionText'])
        self.assertTrue(screenshot_path.endswith('.png'))
        self.assertEqual('daily_note', edits[0]['target']['scope'])
        self.assertEqual(note_id, edits[0]['target']['note_id'])
        self.assertEqual(original_hash, edits[0]['expected_original_hash'])
        self.assertEqual('B2 blue current note', edits[0]['fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual('B2 blue current note', note['body_fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual('#0055aa', note['body_fragment']['blocks'][0]['content'][0]['foreground'])

    def test_shouldLookupCurrentMatrixNoteReferenceAndSaveSignedReceipt(self):
        draft = self.prepared_continuity_draft()
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        completion_posts = []
        save_posts = []

        def record_completion(route):
            completion_posts.append(route.request.post_data or '')
            fulfill_route_response(route, fetch_local_route_response(route))

        def record_save(route):
            save_posts.append(form_fields_from_request(route.request))
            fulfill_route_response(route, fetch_local_route_response(route))

        with project_page(self.live_server_url + reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        })) as page:
            page.route('**/completions/', record_completion)
            page.route('**/save/', record_save)
            region = page.locator(f'[data-continuity-current-note-id="{note_id}"] [data-report-wysiwyg-region]').first
            region.locator('[data-report-editor-surface]').click()
            region.locator('.ProseMirror').wait_for()
            region.locator('.ProseMirror').click()
            page.keyboard.press('Control+A')
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').nth(1).click()
            page.wait_for_function("""
                () => document.querySelector('[data-continuity-matrix] .ProseMirror')
                    ?.textContent.includes('Browser linked title')
            """)
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, response.value.status)

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        note = next(note for note in saved.authoring_context['notes'] if note['note_id'] == note_id)
        edit = next(edit for edit in saved.authored_edits if edit.target == {'scope': 'daily_note', 'note_id': note_id})
        completion_payload = json.loads(completion_posts[0])
        save_payload = json.loads(save_posts[0]['authored_edits'])[0]
        link = note['body_fragment']['blocks'][0]['content'][0]

        self.assertEqual({'scope': 'daily_note', 'note_id': note_id}, completion_payload['region_target'])
        self.assertEqual(1, len(save_payload['reference_receipts']))
        self.assertEqual('link', link['type'])
        self.assertIn('reference_id', link)
        self.assertEqual(1, len(edit.reference_observations))

    def test_shouldPostContinuityChangesThroughActualSaveView(self):
        draft = self.prepared_continuity_draft()
        issue_ref = draft.authoring_context['row_order']['rows'][0]['issue_ref']
        persistent_id = '76000000-0000-4000-8000-000000000211'
        post_data = {
            'payload_version': '2',
            'command_id': draft_command(7200),
            'expected_revision': str(draft.revision),
            'expected_revision_hash': draft.revision_hash,
            'authored_edits': '[]',
            'continuity_changes': json.dumps([{
                'kind': 'add_persistent_note',
                'note_id': persistent_id,
                'target': 'issue',
                'issue_ref': issue_ref,
                'fragment': {
                    'schema_version': 2,
                    'blocks': [{
                        'type': 'paragraph',
                        'content': [{
                            'type': 'text',
                            'text': 'Persistent B2 carry note.',
                            'marks': [],
                            'foreground': None,
                            'background': None,
                        }],
                    }],
                },
                'carry_forward': True,
            }]),
        }
        form = ReportAuthoredSaveForm(post_data, snapshot=draft.snapshot)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.continuity_changes()))
        response = self.client.post(reverse('ui_web:report_draft_save', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        }), post_data, HTTP_ACCEPT='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest', **self.auth('alice'))
        self.assertEqual(200, response.status_code)
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        self.assertEqual(persistent_id, saved.authoring_context['persistent_notes'][0]['note_id'])
        self.assertTrue(saved.authoring_context['persistent_notes'][0]['carry_forward'])

    def test_shouldSaveVisiblePersistentActionAndRowMoveControlsAtomically(self):
        draft = self.prepared_continuity_draft()
        original_rows = tuple(row['issue_ref']['stable_id'] for row in draft.authoring_context['row_order']['rows'])
        action_id = draft.authoring_context['actions'][0]['action_id']
        requests = []

        def record_save(route):
            requests.append(form_fields_from_request(route.request))
            response = fetch_local_route_response(route)
            requests[-1]['__status'] = response.status
            requests[-1]['__body'] = response.body.decode('utf-8', errors='replace')
            fulfill_route_response(route, response)

        with project_page(self.live_server_url + reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        })) as page:
            page.wait_for_selector('[data-continuity-matrix]')
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            persistent = page.locator('[data-continuity-persistent-draft]').first
            persistent.locator('.ProseMirror').wait_for()
            persistent.locator('.ProseMirror').click()
            page.keyboard.type('Visible persistent B2 note')
            page.keyboard.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()

            action = page.locator('[data-continuity-action-control]').first
            action.locator('summary').click()
            action.locator('[data-continuity-action-done]').check()
            action.locator('[data-continuity-action-editor]').click()
            action.locator('.ProseMirror').wait_for()
            action.locator('.ProseMirror').click()
            page.keyboard.type('Resolved visibly in B2.')

            page.locator('[data-continuity-command]').filter(has_text='Move down').first.click()
            page.route('**/save/', record_save)
            with page.expect_response('**/save/') as save_response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, save_response.value.status, requests[0]['__body'])

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        row_order = tuple(row['issue_ref']['stable_id'] for row in saved.authoring_context['row_order']['rows'])
        persistent_note = saved.authoring_context['persistent_notes'][0]
        action = next(action for action in saved.authoring_context['actions'] if action['action_id'] == action_id)
        changes = json.loads(requests[0]['continuity_changes'])

        self.assertEqual({'add_persistent_note', 'set_action_tracking', 'move_row'},
                         {change['kind'] for change in changes})
        self.assertEqual('Visible persistent B2 note', persistent_note['fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual('#0055aa', persistent_note['fragment']['blocks'][0]['content'][0]['foreground'])
        self.assertEqual('done', action['tracking_state'])
        self.assertEqual('Resolved visibly in B2.', action['resolution']['fragment']['blocks'][0]['content'][0]['text'])
        self.assertNotEqual(original_rows, row_order)
