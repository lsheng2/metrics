import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

import pytest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import override_settings
from django.urls import reverse

from project_management.app.api import run_factories
from project_management.app.api.project_runs import (
    ProjectRunRuntime, ProjectRunWorker, build_project_runtime, clear_project_runtime, install_project_runtime,
)
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.services.report_sources import ReportSourceReader
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from project_management.tests.history_persistence_fixtures import history_fixture, publication_file_bytes
from project_management.tests.summary_fixtures import PACK_ROOT
from project_management.tests.test_daily_reprepare_backend import refresh_manual_service
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    BrowserReferenceReader, form_fields_from_request, fragment_text,
)
from ui_web.tests.test_report_daily_ui_views import choice, patch_default_facade, seed_retained_capture
from ui_web.tests.test_report_template_browser import project_page
from ui_web.views.report_completion import ReportDraftCompletionView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='', WHITENOISE_AUTOREFRESH=True)
class TestReportDailyUiBrowser(StaticLiveServerTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = history_fixture(Path(self.temporary.name), actor_subject='basic:alice')
        self.fixture.retained_capture_id = seed_retained_capture(self.fixture)
        reader = ReportSourceReader(self.fixture.archive, AiTaskContract.load(PACK_ROOT))
        self.fixture.source_reader = reader
        self.fixture.continuity.source_reader = reader
        self.fixture.draft_service.source_reader = reader
        self.monkeypatch = pytest.MonkeyPatch()
        self.addCleanup(self.monkeypatch.undo)
        self.sdk_creations = []
        self.monkeypatch.setattr(run_factories, 'TaskRunClient', self.forbid_sdk_client)
        self.facade_context = patch_default_facade(self.monkeypatch, self.fixture)
        self.facade_context.__enter__()
        self.addCleanup(self.facade_context.__exit__, None, None, None)
        self.evidence = Path('.tmp/authoring-main-20261103') / f'daily-ui-browser-{uuid4()}'
        self.evidence.mkdir(parents=True)

    def forbid_sdk_client(self, *args, **kwargs):
        self.sdk_creations.append(True)
        raise AssertionError('Manual preparation must not create an AI client')

    def url(self, name, **extra):
        fixture = self.fixture
        return self.live_server_url + reverse('ui_web:' + name, kwargs={
            'project_id': fixture.project.id,
            'stage_id': fixture.stage.id,
            **extra,
        })

    def preview(self, page, day):
        page.goto(self.url('project_stage_reports'), wait_until='domcontentloaded')
        form = page.locator('[data-report-daily-preview-form]')
        form.locator('[name="series_id"]').select_option(self.fixture.series.series_id)
        form.locator('[name="meeting_date"]').fill(day)
        form.locator('[name="template_choice"]').select_option(choice(self.fixture.template_selection))
        with page.expect_navigation(wait_until='domcontentloaded'):
            form.locator('[data-report-daily-preview]').click()
        page.wait_for_selector('[data-report-daily-baseline]')

    def test_shouldPrepareManualDailyEditPaintReopenFinalizeAndPreviewNextDay(self):
        fixture = self.fixture
        with project_page(self.url('project_stage_reports')) as page:
            page.set_default_navigation_timeout(120000)
            self.preview(page, '2026-11-02')
            form = page.locator('[data-report-daily-prepare-form]')
            form.locator('[name="capture_id"]').select_option(fixture.retained_capture_id)
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.locator('[data-report-daily-generate]').click()
            page.wait_for_selector('[data-report-editor]')
            editor_url = page.url
            draft_id = page.locator('[data-report-editor]').get_attribute('data-draft-id')
            region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
            region.locator('[data-report-editor-surface]').click()
            editor = region.locator('.ProseMirror')
            editor.wait_for()
            editor.fill('Manual Monday validation note.')
            editor.press('Control+a')
            page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
            page.screenshot(path=str(self.evidence / 'monday-edit.png'), full_page=True)
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            save_response = response.value
            fields = form_fields_from_request(save_response.request)
            (self.evidence / 'save-response.json').write_text(json.dumps({
                'status': save_response.status,
                'body': save_response.json(),
                'submitted_fields': {key: value for key, value in fields.items() if key != 'csrfmiddlewaretoken'},
            }, sort_keys=True, indent=2), encoding='utf-8')
            self.assertEqual(200, save_response.status, save_response.text())
            page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
            self.assertEqual('2', page.locator('[data-report-editor]').get_attribute('data-revision'))

        saved = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, draft_id)
        note = next(note for note in saved.authoring_context['notes']
                    if note['meeting']['local_date'] == '2026-11-02')
        self.assertEqual('Manual Monday validation note.', note['body_fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual('#aa0000', note['body_fragment']['blocks'][0]['content'][0]['foreground'])
        before_final = fixture.continuity.preview(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-03',
            template_selection=fixture.template_selection,
        )
        self.assertIsNone(before_final.baseline_ref)
        self.assertEqual((draft_id,), before_final.pending_gap_draft_ids)

        with project_page(editor_url) as page:
            page.set_default_navigation_timeout(120000)
            region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
            painted = region.locator('[style*="color"]').first
            self.assertEqual('rgb(170, 0, 0)', painted.evaluate('(node) => getComputedStyle(node).color'))
            self.assertIn('ww45.1(Fixed):', page.locator('[data-report-editor]').inner_text())
            region.scroll_into_view_if_needed()
            page.screenshot(path=str(self.evidence / 'monday-reopen.png'), full_page=True)
            page.locator('[data-report-finalize-confirm]').check()
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.locator('[data-report-finalize-button]').click()
            self.assertIn('/publications/', page.url)
            publication_id = page.url.rstrip('/').rsplit('/', 1)[-1]
            page.screenshot(path=str(self.evidence / 'monday-finalized.png'), full_page=True)
            self.preview(page, '2026-11-03')
            self.assertIn(publication_id, page.locator('[data-report-daily-baseline]').inner_text())
            page.screenshot(path=str(self.evidence / 'tuesday-baseline.png'), full_page=True)

        after_final = fixture.continuity.preview(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-03',
            template_selection=fixture.template_selection,
        )
        self.assertEqual(publication_id, after_final.baseline_ref.publication_id)
        self.assertEqual((), after_final.pending_gap_draft_ids)
        self.assertEqual([], self.sdk_creations)
        (self.evidence / 'result.json').write_text(json.dumps({
            'browser': 'Chrome',
            'draft_id': draft_id,
            'publication_id': publication_id,
            'note_id': note['note_id'],
            'note_hash': note['body_hash'],
            'before_finalize_baseline': None,
            'after_finalize_baseline': publication_id,
            'sdk_client_creations': len(self.sdk_creations),
        }, sort_keys=True, indent=2), encoding='utf-8')

    def test_shouldCarryEditablePersistentReferenceIntoActualNextDay(self):
        fixture = self.fixture
        evidence = Path('.tmp/dashboard-delivery-20261105') / f'daily-two-day-{uuid4()}'
        evidence.mkdir(parents=True)

        class ScopedReferenceReader(BrowserReferenceReader):
            def read(self, context, member):
                return replace(super().read(context, member),
                               scope_snapshot_hash=context['membership_proof_hash'])

        reader = ScopedReferenceReader()
        verifier = ReferenceReceiptVerifier('synthetic-daily-two-day-only')
        fixture.draft_service.reference_verifier = verifier
        completion = ReportCompletionService(
            fixture.draft_service, fixture.source_reader, reader, verifier,
            CompletionAdmissionStore(fixture.archive.config.root),
        )
        self.monkeypatch.setattr(ReportDraftCompletionView, 'completion_factory', staticmethod(lambda: completion))
        self.monkeypatch.setattr(ReportDraftCompletionView, 'project_api_factory',
                                staticmethod(lambda: fixture.archive.project_api))

        def record_response(response, name):
            payload = {
                'status': response.status,
                'location': response.headers.get('location'),
                'body': None if response.status == 302 else response.text(),
                'submitted_fields': {
                    key: value for key, value in form_fields_from_request(response.request).items()
                    if key != 'csrfmiddlewaretoken'
                },
            }
            (evidence / f'{name}.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
            return payload

        def click_post(page, button, url, name, status):
            started = perf_counter()
            with page.expect_response(lambda response: response.url == url
                                      and response.request.method == 'POST', timeout=120000) as pending:
                button.click(no_wait_after=True)
            payload = record_response(pending.value, name)
            payload['elapsed_seconds'] = round(perf_counter() - started, 3)
            (evidence / f'{name}.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
            self.assertEqual(status, payload['status'], f'Response evidence: {evidence / (name + ".json")}')
            return payload

        def prepare(page, day, name, expected_status=302):
            page.goto(self.url('project_stage_reports'), wait_until='domcontentloaded', timeout=120000)
            preview_form = page.locator('[data-report-daily-preview-form]')
            preview_form.locator('[name="series_id"]').select_option(fixture.series.series_id)
            preview_form.locator('[name="meeting_date"]').fill(day)
            preview_form.locator('[name="template_choice"]').select_option(choice(fixture.template_selection))
            with page.expect_response(lambda response: response.url.startswith(self.url('report_baseline_preview'))
                                      and response.request.method == 'GET', timeout=120000) as pending:
                preview_form.locator('[data-report-daily-preview]').click(no_wait_after=True)
            result = record_response(pending.value, f'{name}-preview')
            self.assertEqual(200, result['status'], f'Preview evidence: {evidence / (name + "-preview.json")}')
            page.wait_for_url(pending.value.url, wait_until='domcontentloaded', timeout=120000)
            page.wait_for_selector('[data-report-daily-baseline]')
            form = page.locator('[data-report-daily-prepare-form]')
            form.locator('[name="capture_id"]').select_option(fixture.retained_capture_id)
            return click_post(page, form.locator('[data-report-daily-generate]'),
                              self.url('report_preparation_create'), name, expected_status)

        def save(page, draft_id, name, revision):
            payload = click_post(page, page.locator('[data-report-save-button]'),
                                 self.url('report_draft_save', draft_id=draft_id), name, 200)
            page.wait_for_function(
                "revision => document.querySelector('[data-report-editor]')?.dataset.revision === revision",
                arg=str(revision),
            )
            return payload

        def finalize(page, draft_id, name):
            page.locator('[data-report-finalize-confirm]').check()
            result = click_post(page, page.locator('[data-report-finalize-button]'),
                                self.url('report_draft_finalize', draft_id=draft_id), name, 302)
            page.wait_for_url('**/publications/*/', timeout=120000)
            page.screenshot(path=str(evidence / f'{name}.png'), full_page=True)
            return result['location'].rstrip('/').rsplit('/', 1)[-1]

        def mount(region):
            region.locator('[data-report-editor-surface]').click()
            editor = region.locator('.ProseMirror')
            editor.wait_for()
            return editor

        current = '[data-report-wysiwyg-region][data-target-json*="daily_note"]'
        href = 'https://tracker.example.test/jira/browse/ALPHA-1'
        with project_page(self.url('project_stage_reports')) as page:
            prepare(page, '2026-11-02', 'monday-prepare')
            page.wait_for_selector('[data-report-editor]')
            monday_id = page.locator('[data-report-editor]').get_attribute('data-draft-id')
            monday_url = page.url
            editor = mount(page.locator(current).first)
            editor.fill('Monday verified fix; retain the human note.')
            editor.press('Control+a')
            page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            persistent = page.locator('[data-continuity-persistent-draft]')
            persistent_id = persistent.get_attribute('data-continuity-persistent-draft')
            persistent.locator('.ProseMirror').fill('Follow ')
            save(page, monday_id, 'monday-new-persistent-save', 2)

            page.goto(monday_url, wait_until='domcontentloaded')
            persistent_selector = f'[data-continuity-persistent-note-id="{persistent_id}"]'
            persistent = page.locator(persistent_selector)
            editor = mount(persistent)
            editor.press('Control+End')
            with page.expect_response('**/completions/') as pending:
                page.keyboard.type('#ALPHA-1')
            result = record_response(pending.value, 'monday-completion')
            self.assertEqual(200, result['status'], result)
            options = page.locator('.report-completion-option')
            options.nth(2).wait_for()
            self.assertEqual(3, options.count())
            page.screenshot(path=str(evidence / 'monday-completion-popup.png'), full_page=True)
            editor.press('ArrowDown')
            editor.press('ArrowDown')
            editor.press('Enter')
            persistent.locator(f'a[href="{href}"]').wait_for()
            self.assertEqual(0, options.count())
            self.assertIn('Browser linked title @Alice', persistent.inner_text())
            saved_response = save(page, monday_id, 'monday-reference-save', 3)
            submitted = json.loads(saved_response['submitted_fields']['authored_edits'])
            reference_edit = next(item for item in submitted if item['target'].get('scope') == 'persistent_note')
            self.assertEqual(1, len(reference_edit['reference_receipts']))

        monday_saved = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, monday_id)
        monday_note = monday_saved.authoring_context['notes'][0]
        monday_persistent = monday_saved.authoring_context['persistent_notes'][0]
        monday_link = next(item for item in monday_persistent['fragment']['blocks'][0]['content']
                           if item['type'] == 'link')
        self.assertEqual('ALPHA-1', monday_link['content'][0]['text'])
        self.assertEqual(href, monday_link['href'])
        self.assertTrue(monday_link['reference_id'])
        self.assertTrue(monday_persistent['carry_forward'])
        before_final = fixture.continuity.preview(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-03',
            template_selection=fixture.template_selection,
        )
        self.assertIsNone(before_final.baseline_ref)
        self.assertEqual((monday_id,), before_final.pending_gap_draft_ids)

        with project_page(monday_url) as page:
            persistent = page.locator(persistent_selector)
            self.assertIn('Follow ALPHA-1 Browser linked title @Alice', persistent.inner_text())
            self.assertEqual('rgb(170, 0, 0)', page.locator(current).first.locator('[style*="color"]').first.evaluate(
                '(node) => getComputedStyle(node).color',
            ))
            persistent.scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / 'monday-reopen.png'), full_page=True)
            monday_publication_id = finalize(page, monday_id, 'monday-finalized')

        monday_final = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, monday_id)
        monday_publication = fixture.draft_service.get_publication(
            fixture.actor, fixture.project.id, fixture.stage.id, monday_publication_id,
        )
        monday_files = publication_file_bytes(fixture, monday_publication)

        with project_page(self.url('project_stage_reports')) as page:
            prepare(page, '2026-11-03', 'tuesday-prepare')
            page.wait_for_selector('[data-report-editor]')
            tuesday_id = page.locator('[data-report-editor]').get_attribute('data-draft-id')
            tuesday_url = page.url
            self.assertNotEqual(monday_id, tuesday_id)
            matrix = page.locator('[data-continuity-matrix]')
            self.assertIn('ww45.1(Fixed):', matrix.inner_text())
            self.assertIn('ww45.2(Fixed):', matrix.inner_text())
            tuesday_cell = matrix.locator('tbody tr').first.locator('td').last
            self.assertLess(tuesday_cell.inner_text().index('ww45.1(Fixed):'),
                            tuesday_cell.inner_text().index('ww45.2(Fixed):'))
            self.assertIn('Monday verified fix; retain the human note.', matrix.inner_text())
            editor = mount(page.locator(current).first)
            editor.fill('Tuesday retest done; no provider status change.')
            persistent = page.locator(persistent_selector)
            editor = mount(persistent)
            self.assertEqual('ALPHA-1', editor.locator('a').inner_text())
            editor.press('Control+End')
            page.keyboard.type(' Tuesday follow-up remains human-owned.')
            editor.press('Control+a')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            page.screenshot(path=str(evidence / 'tuesday-edit.png'), full_page=True)
            save(page, tuesday_id, 'tuesday-save', 2)

        tuesday_saved = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, tuesday_id)
        tuesday_note = next(note for note in tuesday_saved.authoring_context['notes']
                            if note['meeting']['local_date'] == '2026-11-03')
        self.assertEqual('Tuesday retest done; no provider status change.', fragment_text(tuesday_note['body_fragment']))
        tuesday_persistent = tuesday_saved.authoring_context['persistent_notes'][0]
        tuesday_link = next(item for item in tuesday_persistent['fragment']['blocks'][0]['content']
                            if item['type'] == 'link')
        self.assertEqual(monday_link['reference_id'], tuesday_link['reference_id'])
        self.assertEqual(monday_link['href'], tuesday_link['href'])
        self.assertEqual('#0055aa', tuesday_link['content'][0]['foreground'])
        self.assertEqual(monday_note, next(note for note in tuesday_saved.authoring_context['notes']
                                         if note['note_id'] == monday_note['note_id']))
        self.assertIn('Tuesday follow-up remains human-owned.', fragment_text(tuesday_persistent['fragment']))
        inherited = next(edit for edit in tuesday_saved.authored_edits
                         if edit.target == {'scope': 'persistent_note', 'note_id': persistent_id})
        association = inherited.reference_observations[0]['historical_association']
        self.assertEqual('source_publication', association['kind'])
        self.assertEqual(monday_publication_id, association['publication_id'])
        self.assertEqual(monday_publication.manifest_sha256, association['manifest_hash'])
        self.assertEqual(monday_publication.commit_id, association['commit'])
        before_tuesday_final = fixture.continuity.preview(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-04',
            template_selection=fixture.template_selection,
        )
        self.assertEqual(monday_publication_id, before_tuesday_final.baseline_ref.publication_id)

        with project_page(tuesday_url) as page:
            page.locator(current).first.filter(has_text='Tuesday retest done; no provider status change.').wait_for()
            self.assertIn('Tuesday retest done; no provider status change.', page.locator(current).first.inner_text())
            persistent = page.locator(persistent_selector)
            link = persistent.locator(f'a[href="{href}"]')
            self.assertIn('Tuesday follow-up remains human-owned.', persistent.inner_text())
            self.assertEqual('rgb(0, 85, 170)', link.locator('[style*="color"]').first.evaluate(
                '(node) => getComputedStyle(node).color',
            ))
            persistent.scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / 'tuesday-reopen.png'), full_page=True)
            tuesday_publication_id = finalize(page, tuesday_id, 'tuesday-finalized')
            self.assertNotEqual(monday_publication_id, tuesday_publication_id)
            prepare(page, '2026-11-03', 'tuesday-reuse', expected_status=409)
            existing = page.locator('[data-report-daily-result]')
            self.assertIn('Existing preparation', existing.inner_text())
            self.assertIn('Unapplied choices: baseline', existing.inner_text())
            publication_link = existing.get_by_role('link', name='Published report', exact=True)
            expected_url = self.url('report_publication', publication_id=tuesday_publication_id)
            self.assertEqual(expected_url, self.live_server_url + publication_link.get_attribute('href'))
            publication_link.click(no_wait_after=True)
            page.wait_for_url(expected_url, wait_until='domcontentloaded', timeout=120000)

        after_final = fixture.continuity.preview(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-04',
            template_selection=fixture.template_selection,
        )
        self.assertEqual(tuesday_publication_id, after_final.baseline_ref.publication_id)
        self.assertEqual((), after_final.pending_gap_draft_ids)
        drafts = fixture.draft_service.list_drafts(fixture.actor, fixture.project.id, fixture.stage.id)
        self.assertEqual({monday_id, tuesday_id}, {item.draft_id for item in drafts.items})
        retained = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, monday_id)
        self.assertEqual(monday_final.revision_hash, retained.revision_hash)
        self.assertEqual(monday_final.authoring_context, retained.authoring_context)
        retained_publication = fixture.draft_service.get_publication(
            fixture.actor, fixture.project.id, fixture.stage.id, monday_publication_id,
        )
        self.assertEqual(monday_publication.manifest_sha256, retained_publication.manifest_sha256)
        self.assertEqual(monday_publication.commit_id, retained_publication.commit_id)
        self.assertEqual(monday_files, publication_file_bytes(fixture, retained_publication))
        tuesday_publication = fixture.draft_service.get_publication(
            fixture.actor, fixture.project.id, fixture.stage.id, tuesday_publication_id,
        )
        self.assertEqual(tuesday_id, tuesday_publication.manifest.draft_id)
        self.assertEqual(tuesday_saved.revision, tuesday_publication.manifest.draft_revision)
        self.assertNotEqual(monday_publication.commit_id, tuesday_publication.commit_id)
        self.assertEqual(tuesday_publication.manifest_sha256, after_final.baseline_ref.manifest_hash)
        self.assertEqual(tuesday_publication.commit_id, after_final.baseline_ref.commit)
        tuesday_html = fixture.draft_service.read_artifact(
            fixture.actor, fixture.project.id, fixture.stage.id, tuesday_publication_id, 'html',
        )
        self.assertIn(b'Tuesday retest done; no provider status change.', tuesday_html)
        self.assertIn(b'Monday verified fix; retain the human note.', tuesday_html)
        self.assertIn(href.encode('utf-8'), tuesday_html)
        (evidence / 'tuesday-report.html').write_bytes(tuesday_html)
        self.assertEqual(1, len(reader.calls), 'Tuesday must validate the publication association without a new lookup')
        self.assertEqual([], self.sdk_creations)
        (evidence / 'result.json').write_text(json.dumps({
            'monday_draft_id': monday_id, 'tuesday_draft_id': tuesday_id,
            'monday_revision_hash': monday_final.revision_hash,
            'tuesday_revision_hash': tuesday_saved.revision_hash,
            'monday_note_hash': monday_note['body_hash'],
            'tuesday_note_hash': tuesday_note['body_hash'],
            'monday_publication_id': monday_publication_id, 'tuesday_publication_id': tuesday_publication_id,
            'monday_file_hashes': {name: sha256(data).hexdigest() for name, data in monday_files.items()},
            'tuesday_html_hash': sha256(tuesday_html).hexdigest(),
            'persistent_note_id': persistent_id, 'reference_id': monday_link['reference_id'],
            'historical_association': association, 'reference_lookups': len(reader.calls),
            'sdk_client_creations': len(self.sdk_creations),
        }, sort_keys=True, indent=2), encoding='utf-8')

    def test_shouldRefreshThroughRegisteredWorkerAndReuseSameMeetingFromVisibleControls(self):
        fixture = self.fixture
        _, service = refresh_manual_service(fixture, ({
            'stable_id': 'ALPHA-1', 'summary': 'Fresh manual capture', 'status': 'Fixed',
        },))
        runtime = ProjectRunRuntime(service, ProjectRunWorker(service))
        with override_settings(METRICS_PROJECT_RUNTIME_FACTORY=lambda: runtime):
            runtime = build_project_runtime()
        installed_preparation = runtime.worker.daily_preparation_service
        install_project_runtime(runtime)
        self.addCleanup(clear_project_runtime, runtime)
        close_worker_connections_after_execute(runtime.worker)
        runtime.start()
        self.addCleanup(self.stop_runtime, runtime)

        with project_page(self.url('project_stage_reports')) as page:
            page.set_default_navigation_timeout(120000)
            self.preview(page, '2026-11-02')
            form = page.locator('[data-report-daily-prepare-form]')
            form.locator('[name="capture_id"]').select_option(fixture.retained_capture_id)
            form.locator('[name="source_mode"]').select_option('refresh')
            self.assertEqual('', form.locator('[name="capture_id"]').input_value())
            self.assertTrue(form.locator('[name="analysis_mode"] option[value="changed_items"]').is_disabled())
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.locator('[data-report-daily-generate]').click()
            page.wait_for_function("""() => ['partial', 'draft_ready', 'failed', 'canceled'].includes(
                document.querySelector('#project-run-status-fragment h2')?.textContent.trim()
            )""", timeout=120000)
            operation_id = page.locator('#project-run-status-fragment').get_attribute('data-operation-id')
            self.assertEqual('partial', page.locator('#project-run-status-fragment h2').inner_text())
            page.screenshot(path=str(self.evidence / 'refresh-terminal.png'), full_page=True)
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.get_by_role('link', name='Open latest draft').click()
            self.assertIn('ww45.1(Fixed):', page.locator('[data-report-editor]').inner_text())
            self.preview(page, '2026-11-02')
            form = page.locator('[data-report-daily-prepare-form]')
            form.locator('[name="source_mode"]').select_option('refresh')
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.locator('[data-report-daily-generate]').click()
            self.assertEqual(operation_id, page.locator('#project-run-status-fragment').get_attribute('data-operation-id'))

        self.assertEqual(1, len(service.list(fixture.actor, fixture.project.id, fixture.stage.id)))
        self.assertIs(installed_preparation, runtime.worker.daily_preparation_service)
        self.assertEqual([], self.sdk_creations)

    def stop_runtime(self, runtime):
        result = runtime.stop(60)
        self.assertTrue(result.stopped, result)
        self.assertFalse(result.unresolved, result)

    def test_shouldReprepareFromVisibleDetailsWithoutChangingOriginalHumanNote(self):
        fixture = self.fixture
        with project_page(self.url('project_stage_reports')) as page:
            page.set_default_navigation_timeout(120000)
            self.preview(page, '2026-11-02')
            form = page.locator('[data-report-daily-prepare-form]')
            form.locator('[name="capture_id"]').select_option(fixture.retained_capture_id)
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.locator('[data-report-daily-generate]').click()
            original_id = page.locator('[data-report-editor]').get_attribute('data-draft-id')
            region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
            region.locator('[data-report-editor-surface]').click()
            editor = region.locator('.ProseMirror')
            editor.wait_for()
            editor.fill('Human blue note before rebuilding.')
            editor.press('Control+a')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, response.value.status, response.value.text())
            page.wait_for_function("document.querySelector('[data-report-editor]')?.dataset.revision === '2'")
            original = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, original_id)
            self.preview(page, '2026-11-02')
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.get_by_role('link', name='Open existing preparation').click()
            original_preparation_url = page.url
            page.screenshot(path=str(self.evidence / 'before-reprepare.png'), full_page=True)
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.locator('[data-report-reprepare]').click()
            self.assertNotEqual(original_preparation_url, page.url)
            self.assertTrue(page.get_by_role('link', name='Original preparation').is_visible())
            with page.expect_navigation(wait_until='domcontentloaded'):
                page.get_by_role('link', name='Open draft').click()
            replacement_id = page.locator('[data-report-editor]').get_attribute('data-draft-id')
            self.assertNotEqual(original_id, replacement_id)
            region = page.locator('[data-report-wysiwyg-region][data-target-json*="daily_note"]').first
            self.assertIn('Human blue note before rebuilding.', region.inner_text())
            self.assertEqual('rgb(0, 85, 170)', region.locator('[style*="color"]').first.evaluate(
                '(node) => getComputedStyle(node).color',
            ))
            region.scroll_into_view_if_needed()
            page.screenshot(path=str(self.evidence / 'reprepared-blue-note.png'), full_page=True)

        retained = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, original_id)
        self.assertEqual(original.revision_hash, retained.revision_hash)
        self.assertEqual([], self.sdk_creations)


def close_worker_connections_after_execute(worker):
    execute = worker.execute

    def execute_then_close(*args, **kwargs):
        try:
            return execute(*args, **kwargs)
        finally:
            # The sqlite backend ignores close() on in-memory test databases, so this worker thread's
            # connection would otherwise wait for garbage collection and warn as an unclosed database.
            for connection in connections.all(initialized_only=True):
                BaseDatabaseWrapper.close(connection)

    worker.execute = execute_then_close
