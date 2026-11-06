import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from project_management.app.api import run_factories
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.report_sources import ReportSourceReader
from project_management.tests.history_persistence_fixtures import history_fixture, publication_file_bytes
from project_management.tests.summary_fixtures import PACK_ROOT
from project_management.tests.test_report_meeting_resumption import iso_calendar
from project_management.tests.test_report_template_compilation import matrix_block
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_report_daily_ui_views import choice, patch_default_facade, seed_retained_capture
from ui_web.tests.test_report_template_browser import project_page


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportMeetingBrowser(StaticLiveServerTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        document = {'schema_version': 2, 'report_kind': 'daily',
                    'presentation_profile': 'standup/1', 'blocks': [matrix_block()]}
        self.fixture = history_fixture(Path(self.temporary.name), document=document, actor_subject='basic:alice')
        iso_calendar(self.fixture)
        self.fixture.retained_capture_id = seed_retained_capture(self.fixture)
        reader = ReportSourceReader(self.fixture.archive, AiTaskContract.load(PACK_ROOT))
        self.fixture.source_reader = reader
        self.fixture.continuity.source_reader = reader
        self.fixture.draft_service.source_reader = reader
        self.monkeypatch = pytest.MonkeyPatch()
        self.addCleanup(self.monkeypatch.undo)
        self.sdk_calls = []
        self.monkeypatch.setattr(run_factories, 'TaskRunClient', self.forbid_model)
        self.facade_patch = patch_default_facade(self.monkeypatch, self.fixture)
        self.facade_patch.__enter__()
        self.addCleanup(self.facade_patch.__exit__, None, None, None)
        self.evidence = Path('.tmp/dashboard-skips-20261106') / f'browser-{uuid4()}'
        self.evidence.mkdir(parents=True)

    def forbid_model(self, *args, **kwargs):
        self.sdk_calls.append(True)
        raise AssertionError('Calendar/manual resumption must not create an AI client')

    def url(self, name, **extra):
        return self.live_server_url + reverse('ui_web:' + name, kwargs={
            'project_id': self.fixture.project.id, 'stage_id': self.fixture.stage.id, **extra,
        })

    def preview(self, page, day):
        page.goto(self.url('project_stage_reports'), wait_until='domcontentloaded')
        form = page.locator('[data-report-daily-preview-form]')
        form.locator('[name="series_id"]').select_option(self.fixture.series.series_id)
        form.locator('[name="meeting_date"]').fill(day)
        form.locator('[name="template_choice"]').select_option(choice(self.fixture.template_selection))
        with page.expect_navigation(wait_until='domcontentloaded'):
            form.locator('[data-report-daily-preview]').click()

    def prepare(self, page, day):
        self.preview(page, day)
        form = page.locator('[data-report-daily-prepare-form]')
        form.locator('[name="capture_id"]').select_option(self.fixture.retained_capture_id)
        with page.expect_navigation(wait_until='domcontentloaded'):
            form.locator('[data-report-daily-generate]').click()
        page.locator('[data-report-editor]').wait_for()
        return page.locator('[data-report-editor]').get_attribute('data-draft-id')

    def current_editor(self, page):
        region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
        region.locator('[data-report-editor-surface]').click()
        editor = region.locator('.ProseMirror')
        editor.wait_for()
        return editor

    def save(self, page):
        with page.expect_response('**/save/') as response:
            page.locator('[data-report-save-button]').click()
        self.assertEqual(200, response.value.status, response.value.text())
        page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
        page.goto(page.url, wait_until='domcontentloaded')

    def finalize(self, page):
        page.locator('[data-report-finalize-confirm]').check()
        with page.expect_navigation(wait_until='domcontentloaded'):
            page.locator('[data-report-finalize-button]').click()
        self.assertIn('/publications/', page.url)
        return page.url.rstrip('/').rsplit('/', 1)[-1]

    def calendar(self, page, start='2026-11-09', end='2026-11-22'):
        page.goto(self.url('report_meetings'), wait_until='domcontentloaded')
        query = page.locator('[data-meeting-query-form]')
        query.locator('[name="series_id"]').select_option(self.fixture.series.series_id)
        query.locator('[name="from_date"]').fill(start)
        query.locator('[name="through_date"]').fill(end)
        with page.expect_navigation(wait_until='domcontentloaded'):
            query.locator('button[type="submit"]').click()

    def test_skip_two_weeks_then_resume_real_editor_and_publication(self):
        fixture = self.fixture
        with project_page(self.url('project_stage_reports')) as page:
            page.set_default_navigation_timeout(120000)
            friday_id = self.prepare(page, '2026-11-06')
            editor = self.current_editor(page)
            editor.fill('Friday human note. Validation follow-up remains open.')
            editor.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            persistent = page.locator('[data-continuity-persistent-draft]')
            persistent.locator('.ProseMirror').fill('AR: @Alice confirm validation after the break.')
            self.save(page)
            page.screenshot(path=str(self.evidence / 'friday-saved.png'), full_page=True)
            friday_publication_id = self.finalize(page)

        friday = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, friday_id)
        first = fixture.draft_service.get_publication(
            fixture.actor, fixture.project.id, fixture.stage.id, friday_publication_id,
        )
        before = publication_file_bytes(fixture, first)
        original_note = friday.authoring_context['notes'][0]
        original_persistent = friday.authoring_context['persistent_notes'][0]
        with self.monkeypatch.context() as no_source:
            no_source.setattr(fixture.source_reader, 'read', lambda *a, **k: self.fail('Skip read report source'))
            with project_page(self.url('report_meetings')) as page:
                page.set_default_navigation_timeout(120000)
                self.calendar(page)
                form = page.locator('[data-meeting-change-form]')
                form.locator('[name="reason"]').fill('Planning break')
                with page.expect_navigation(wait_until='domcontentloaded'):
                    form.locator('button[value="skip"]').click()
                self.assertEqual(14, page.locator('[data-meeting-state="skipped"]').count())
                page.screenshot(path=str(self.evidence / 'skipped-desktop.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(self.evidence / 'skipped-phone.png'), full_page=True)
                page.set_viewport_size({'width': 1440, 'height': 900})
                self.preview(page, '2026-11-10')
                self.assertTrue(page.locator('[data-report-daily-generate]').is_disabled())
                self.assertIn('marked skipped', page.locator('[data-report-daily-baseline]').inner_text())

        self.assertEqual(before, publication_file_bytes(fixture, first))
        with project_page(self.url('project_stage_reports')) as page:
            page.set_default_navigation_timeout(120000)
            monday_id = self.prepare(page, '2026-11-23')
            self.assertIn('Standups skipped:', page.locator('[data-meeting-skips]').inner_text())
            self.assertIn('Friday human note.', page.locator('[data-report-editor]').inner_text())
            self.assertIn('AR: @Alice confirm validation after the break.', page.locator('[data-report-editor]').inner_text())
            painted = page.locator('[data-report-editor] [style*="color: #aa0000"], [data-report-editor] [style*="color:#aa0000"]').first
            self.assertEqual('rgb(170, 0, 0)', painted.evaluate('(node) => getComputedStyle(node).color'))
            editor = self.current_editor(page)
            editor.fill('Monday resumed. Validation follow-up confirmed.')
            editor.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            self.save(page)
            page.screenshot(path=str(self.evidence / 'monday-saved.png'), full_page=True)
            monday_publication_id = self.finalize(page)
            with page.expect_download() as pending:
                page.get_by_role('link', name='Download HTML', exact=True).click()
            pending.value.save_as(self.evidence / 'report.html')
            for name, filename in (('markdown', 'report.md'), ('xlsx', 'report.xlsx')):
                page.locator('[data-report-export-format]').select_option(name)
                with page.expect_download() as pending:
                    page.locator('[data-report-export-link]').click()
                pending.value.save_as(self.evidence / filename)
            self.calendar(page)
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.locator('[data-meeting-change-form] button[value="restore"]').click()
            self.assertEqual(14, page.locator('[data-meeting-state="unrecorded"]').count())
            page.screenshot(path=str(self.evidence / 'restored.png'), full_page=True)

        monday = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, monday_id)
        inherited = next(note for note in monday.authoring_context['notes'] if note['note_id'] == original_note['note_id'])
        self.assertEqual(original_note, inherited)
        self.assertEqual(original_persistent, monday.authoring_context['persistent_notes'][0])
        self.assertEqual(14, len(monday.authoring_context['meeting_skips']['days']))
        second = fixture.draft_service.get_publication(
            fixture.actor, fixture.project.id, fixture.stage.id, monday_publication_id,
        )
        after = publication_file_bytes(fixture, second)
        self.assertEqual(before, publication_file_bytes(fixture, first))
        self.assertEqual(after['report.html'], (self.evidence / 'report.html').read_bytes())
        self.assertIn('Standups skipped:', (self.evidence / 'report.md').read_text(encoding='utf-8'))
        import openpyxl

        workbook = openpyxl.load_workbook(self.evidence / 'report.xlsx', read_only=True)
        try:
            self.assertTrue(any('Standups skipped:' in str(row[0])
                                for row in workbook['Report text'].iter_rows(values_only=True)))
        finally:
            workbook.close()
        self.assertEqual([], self.sdk_calls)
        self.assertEqual(2, len(fixture.draft_service.list_drafts(fixture.actor, fixture.project.id, fixture.stage.id).items))
        for label, files in (('friday', before), ('monday', after)):
            target = self.evidence / label
            target.mkdir()
            for name, content in files.items():
                (target / name).write_bytes(content)
        (self.evidence / 'result.json').write_text(json.dumps({
            'status': 'passed', 'friday_publication': friday_publication_id,
            'monday_publication': monday_publication_id, 'skipped_dates': 14, 'drafts': 2,
            'original_note_hash': original_note['body_hash'], 'sdk_calls': len(self.sdk_calls),
            'real_provider_calls': 0, 'real_model_calls': 0,
            'friday_files': {name: sha256(content).hexdigest() for name, content in before.items()},
            'monday_files': {name: sha256(content).hexdigest() for name, content in after.items()},
        }, indent=2), encoding='utf-8')

    def test_chinese_calendar_controls_fit_phone_and_preserve_selection(self):
        with project_page(self.url('report_meetings')) as page:
            page.set_default_navigation_timeout(120000)
            self.calendar(page, '2026-11-09', '2026-11-09')
            language = page.locator('form:has(select[name="language"])')
            language.locator('select').select_option('zh-hans')
            with page.expect_navigation(wait_until='domcontentloaded'):
                language.locator('button').click()
            self.assertEqual('zh-hans', page.locator('html').get_attribute('lang'))
            self.assertIn('\u4f1a\u8bae\u65e5\u5386', page.locator('h2').inner_text())
            self.assertEqual('2026-11-09', page.locator('[data-meeting-query-form] [name="from_date"]').input_value())
            page.set_viewport_size({'width': 390, 'height': 844})
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            self.assertTrue(page.get_by_role('button', name='\u6807\u8bb0\u505c\u4f1a', exact=True).is_visible())
            ids = page.locator('[data-meeting-query-form] [id], [data-meeting-change-form] [id]').evaluate_all(
                '(nodes) => nodes.map(node => node.id)',
            )
            self.assertEqual(len(ids), len(set(ids)))
            page.screenshot(path=str(self.evidence / 'calendar-zh-phone.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.screenshot(path=str(self.evidence / 'calendar-zh-desktop.png'), full_page=True)
