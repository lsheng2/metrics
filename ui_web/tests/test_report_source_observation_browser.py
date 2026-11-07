from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

from django.test import override_settings

from project_management.tests.history_persistence_fixtures import daily_note_edit, ref_for
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_source_observations import manual_source
from project_management.tests.test_report_standup import standup_document
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestSourceObservationBrowser(ReportHistoryUiBrowserSupport):
    def test_manual_no_change_is_readonly_bilingual_and_replaced_after_saving_a_human_note(self):
        source = manual_source()
        self.source.snapshot = replace(
            source, rows=(replace(source.rows[0], title='Validation follow-up', status='In Analysis'),),
            coverage={'complete': False, 'accepted_count': 0, 'pending_count': 1},
        )
        args = self.actor, self.project.id, self.stage.id
        setup = self.continuity_setup(15000, document=standup_document())
        monday = self.prepared_continuity_draft(setup=setup, command_index=15002)
        note_id = monday.authoring_context['current_observations'][0]['note_id']
        saved = self.service.save_authored(
            *args, monday.draft_id, command_id=draft_command(15003),
            expected_revision=monday.revision, expected_revision_hash=monday.revision_hash,
            edits=(daily_note_edit(15003, note_id, 'Monday human note.', '#aa0000', None),),
        )
        publication = self.service.finalize_and_commit(
            *args, monday.draft_id, command_id=draft_command(15004), expected_revision=saved.revision,
        )
        self.source.source_commit = publication.commit_id
        self.archive.capture_id = '99999999-9999-4999-8999-999999999998'
        self.source.snapshot = replace(
            self.source.snapshot, source_as_of='2026-11-03T01:00:00Z', report_date='2026-11-03',
        )
        tuesday = self.prepared_continuity_draft(
            setup=setup, command_index=15005, meeting_date='2026-11-03', baseline=ref_for(publication),
        )
        current_id = tuesday.authoring_context['current_observations'][0]['note_id']
        selector = f'[data-continuity-current-note-id="{current_id}"]'
        evidence = Path('.tmp/dashboard-source-observation-20261107') / f'browser-{uuid4()}'
        evidence.mkdir(parents=True)
        measurements = []

        for language, label in (('en', 'No source change'), ('zh-hans', '\u6765\u6e90\u672a\u53d8\u5316')):
            with project_page(self.editor_url(tuesday.draft_id), language=language) as page:
                page.set_default_timeout(15000)
                notice = page.locator('[data-matrix-source-observation]')
                self.assertEqual(label, notice.inner_text())
                self.assertFalse(notice.evaluate('(node) => Boolean(node.closest("[data-report-wysiwyg-region]"))'))
                region = page.locator(selector)
                region.locator('[data-report-editor-surface]').click()
                editor = region.locator('.ProseMirror')
                editor.wait_for()
                self.assertEqual('', editor.inner_text().strip())
                self.assertIn('Monday human note.', page.locator('[data-continuity-matrix]').inner_text())
                self.assertEqual('rgb(170, 0, 0)', page.locator('[data-matrix-readonly-note] [style*="color"]').last.evaluate(
                    '(node) => getComputedStyle(node).color',
                ))
                for width, height in ((1440, 900), (390, 844)):
                    page.set_viewport_size({'width': width, 'height': height})
                    notice.scroll_into_view_if_needed()
                    metrics = page.evaluate(r"""() => {
                        const node = document.querySelector('[data-matrix-source-observation]');
                        const rect = node.getBoundingClientRect();
                        const luminance = color => color.match(/\d+/g).slice(0, 3)
                            .map(value => Number(value) / 255)
                            .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
                            .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
                        const foreground = luminance(getComputedStyle(node).color);
                        const background = luminance(getComputedStyle(node.closest('td')).backgroundColor);
                        return {width: innerWidth, pageWidth: document.documentElement.scrollWidth,
                                noticeWidth: rect.width, noticeHeight: rect.height,
                                textFits: node.scrollWidth <= node.clientWidth,
                                contrast: (Math.max(foreground, background) + 0.05)
                                    / (Math.min(foreground, background) + 0.05)};
                    }""")
                    self.assertLessEqual(metrics['pageWidth'], width)
                    self.assertTrue(metrics['textFits'])
                    self.assertGreater(metrics['noticeWidth'], 0)
                    self.assertGreater(metrics['noticeHeight'], 0)
                    self.assertGreaterEqual(metrics['contrast'], 4.5)
                    measurements.append({'language': language, **metrics})
                    page.screenshot(path=str(evidence / f'{language}-{width}.png'), full_page=True)
                if language == 'zh-hans':
                    editor.fill('Tuesday human note.')
                    editor.press('Control+A')
                    page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
                    with page.expect_response('**/save/') as response:
                        page.locator('[data-report-save-button]').click()
                    self.assertEqual(200, response.value.status, response.value.text())
                    page.wait_for_function("""() =>
                        document.querySelector('[data-report-editor]')?.dataset.revision === '2'
                        && !document.querySelector('[data-matrix-source-observation]')""")
                    page.locator(selector).filter(has_text='Tuesday human note.').wait_for()
                    self.assertIn('Tuesday human note.', page.locator(selector).inner_text())
                    page.screenshot(path=str(evidence / 'saved-human-note-zh-hans.png'), full_page=True)

        reopened = self.service.get(*args, tuesday.draft_id)
        current = next(note for note in reopened.authoring_context['notes'] if note['note_id'] == current_id)
        self.assertEqual('Tuesday human note.', current['body_fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual('#0055aa', current['body_fragment']['blocks'][0]['content'][0]['foreground'])
        self.assertEqual(saved.authoring_context['notes'][0], reopened.authoring_context['notes'][0])
        rendered = self.service.render(*args, reopened.draft_id, revision=reopened.revision)
        self.assertIn('ww45.2(In Analysis): Tuesday human note.', rendered.plain_text)
        self.assertNotIn('No source change', rendered.plain_text)
        (evidence / 'result.json').write_text(json.dumps({
            'status': 'passed', 'measurements': measurements,
            'draft_id': tuesday.draft_id, 'revision': reopened.revision,
            'real_provider_calls': 0, 'real_model_calls': 0,
        }, indent=2), encoding='utf-8')
