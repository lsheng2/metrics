import json
from urllib.parse import quote

from django.test import override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.report_draft_fixtures import draft_command
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    fetch_local_route_response,
    form_fields_from_request,
    fulfill_route_response,
)
from ui_web.report_template_documents import continuity_starter_document, default_fill_policy
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportHistoryUiRoutesBrowser(ReportHistoryUiBrowserSupport):
    def test_shouldAddReportPersistentAndEditClearCarryExistingPersistentVisibly(self):
        draft = self.prepared_continuity_draft()
        issue_ref = draft.authoring_context['row_order']['rows'][0]['issue_ref']
        existing_id = '76000000-0000-4000-8000-000000000311'
        seeded = self.service.save_authored(
            self.actor, self.project.id, self.stage.id, draft.draft_id,
            command_id=draft_command(7710), expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash, edits=(),
            continuity_changes=({'kind': 'add_persistent_note', 'note_id': existing_id, 'target': 'issue',
                                 'issue_ref': issue_ref, 'fragment': plain_fragment('Existing carry note.'),
                                 'carry_forward': True},),
        )
        requests = []

        def record_save(route):
            requests.append(form_fields_from_request(route.request))
            response = fetch_local_route_response(route)
            requests[-1]['__body'] = response.body.decode('utf-8', errors='replace')
            fulfill_route_response(route, response)

        with project_page(self.editor_url(seeded.draft_id)) as page:
            page.wait_for_selector(f'[data-continuity-persistent-note-id="{existing_id}"] [data-report-wysiwyg-region]')
            existing = page.locator(f'[data-continuity-persistent-note-id="{existing_id}"] [data-report-wysiwyg-region]').first
            existing.locator('[data-report-editor-surface]').click()
            existing.locator('.ProseMirror').wait_for()
            existing.locator('.ProseMirror').click()
            page.keyboard.press('Control+A')
            page.keyboard.press('Backspace')
            page.locator(f'[data-continuity-persistent-note-id="{existing_id}"] [data-continuity-change]').uncheck()
            page.locator('[data-persistent-target="report"]').click()
            report_persistent = page.locator('[data-continuity-report-persistent-list] [data-continuity-persistent-draft]').first
            report_persistent.locator('.ProseMirror').wait_for()
            report_persistent.locator('.ProseMirror').click()
            page.keyboard.type('Report persistent visible note.')
            page.route('**/save/', record_save)
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, response.value.status, requests[0]['__body'])

        saved = self.service.get(self.actor, self.project.id, self.stage.id, seeded.draft_id)
        by_id = {note['note_id']: note for note in saved.authoring_context['persistent_notes']}
        changes = json.loads(requests[0]['continuity_changes'])
        self.assertEqual((), by_id[existing_id]['fragment']['blocks'][0]['content'])
        self.assertFalse(by_id[existing_id]['carry_forward'], changes)
        self.assertTrue(any(change['kind'] == 'add_persistent_note' and change['target'] == 'report'
                            and change['issue_ref'] is None for change in changes))

    def test_lostSaveRetriesOriginalContinuityPayloadAndKeepsNewerPersistentEditDirty(self):
        draft = self.prepared_continuity_draft()
        posts = []
        first = {'done': False}

        def lost_first_then_replay(route):
            posts.append(form_fields_from_request(route.request))
            if not first['done']:
                first['done'] = True
                fetch_local_route_response(route)
                route.abort()
                return
            fulfill_route_response(route, fetch_local_route_response(route))

        with project_page(self.editor_url(draft.draft_id)) as page:
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            persistent = page.locator('[data-continuity-persistent-draft]').first
            persistent.locator('.ProseMirror').wait_for()
            persistent.locator('.ProseMirror').click()
            page.keyboard.type('Original persistent A')
            page.route('**/save/', lost_first_then_replay)
            page.locator('[data-report-save-button]').click()
            page.wait_for_function("document.querySelector('[data-report-editor]').dataset.reportAuthoringError")
            persistent.locator('.ProseMirror').click()
            page.keyboard.type(' newer B')
            page.locator('[data-report-save-button]').click()
            page.wait_for_function("document.querySelector('[data-report-copy-status]').textContent.includes('Saved') || document.querySelector('[data-report-copy-status]').textContent.includes('ready')")
            state = page.evaluate("""
                () => ({
                    text: document.querySelector('[data-continuity-persistent-draft] .ProseMirror').textContent,
                    dirty: document.querySelector('[data-report-editor]').dataset.reportAuthoringDirty,
                })
            """)

        self.assertEqual(2, len(posts))
        self.assertEqual(posts[0]['command_id'], posts[1]['command_id'])
        self.assertEqual(posts[0]['continuity_changes'], posts[1]['continuity_changes'])
        self.assertIn('Original persistent A newer B', state['text'])
        self.assertEqual('true', state['dirty'])

    def test_shouldDestroyLateContinuityMountAndAvoidDuplicateEventsAfterRemount(self):
        draft = self.prepared_continuity_draft()
        with project_page(self.editor_url(draft.draft_id)) as page:
            page.evaluate("""
                () => {
                    window.__continuityDestroyed = 0;
                    window.__resolveContinuityRuntime = null;
                    window.__originalRuntime = window.ReportMilkdownEditor.createRuntime;
                    window.ReportMilkdownEditor.createRuntime = async (element, fragment) => {
                        return await new Promise(resolve => {
                            window.__resolveContinuityRuntime = () => resolve({
                                getFragment: () => fragment,
                                replaceFragment: () => {},
                                command: () => true,
                                findToken: () => null,
                                destroy: () => { window.__continuityDestroyed += 1; },
                            });
                        });
                    };
                }
            """)
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            page.wait_for_function("typeof window.__resolveContinuityRuntime === 'function'")
            page.evaluate("""
                async () => {
                    const root = document.querySelector('[data-report-editor]');
                    root.__reportAuthoring.destroy();
                    document.querySelector('[data-continuity-persistent-draft]')?.remove();
                    window.__resolveContinuityRuntime();
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            """)
            page.wait_for_function("window.__continuityDestroyed === 1")
            page.evaluate("""
                async () => {
                    window.ReportMilkdownEditor.createRuntime = window.__originalRuntime;
                    window.__continuityEvents = 0;
                    const root = document.querySelector('[data-report-editor]');
                    root.addEventListener('report-continuity-change', () => { window.__continuityEvents += 1; });
                    const module = await import('/static/js/report_editor/index.js');
                    module.initializeReportAuthoring(root);
                }
            """)
            page.locator('[data-continuity-matrix] [data-continuity-add-persistent]').first.click()
            page.wait_for_function("window.__continuityEvents === 1")

        self.assertTrue(True)

    def test_shouldEditActionNarrativeThroughVisibleMatrixControl(self):
        draft = self.prepared_continuity_draft()
        action_id = draft.authoring_context['actions'][0]['action_id']
        requests = []

        def record_save(route):
            requests.append(form_fields_from_request(route.request))
            response = fetch_local_route_response(route)
            requests[-1]['__body'] = response.body.decode('utf-8', errors='replace')
            fulfill_route_response(route, response)

        with project_page(self.editor_url(draft.draft_id)) as page:
            page.wait_for_selector(f'[data-matrix-action-body] [data-report-wysiwyg-region][data-target-json*="{action_id}"]')
            action_region = page.locator(f'[data-matrix-action-body] [data-report-wysiwyg-region][data-target-json*="{action_id}"]').first
            action_region.locator('[data-report-editor-surface]').click()
            action_region.locator('.ProseMirror').wait_for()
            action_region.locator('.ProseMirror').click()
            page.keyboard.press('Control+A')
            page.keyboard.type('Edited visible AR narrative.')
            page.route('**/save/', record_save)
            with page.expect_response('**/save/') as response:
                page.locator('[data-report-save-button]').click()
            self.assertEqual(200, response.value.status, requests[0]['__body'])

        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)
        action = next(action for action in saved.authoring_context['actions'] if action['action_id'] == action_id)
        edits = json.loads(requests[0]['authored_edits'])
        self.assertEqual('Edited visible AR narrative.', action['body_fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual({'scope': 'report_action', 'action_id': action_id}, edits[0]['target'])

    def test_shouldRenderHistoricalMatrixNoteReadonlyAndCurrentDayEditable(self):
        setup = self.continuity_setup(7300)
        day1 = self.prepared_continuity_draft(setup=setup, command_index=7310, meeting_date='2026-11-03')
        note_id = day1.authoring_context['current_observations'][0]['note_id']
        original = next(note for note in day1.authoring_context['notes'] if note['note_id'] == note_id)
        saved_day1 = self.service.save_authored(
            self.actor, self.project.id, self.stage.id, day1.draft_id,
            command_id=draft_command(7311), expected_revision=day1.revision,
            expected_revision_hash=day1.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '73000000-0000-4000-8000-000000007311', 'note',
                {'scope': 'daily_note', 'note_id': note_id},
                plain_fragment('Day1 readonly blue note.', foreground='#0055aa'), original['body_hash'],
            ),),
        )
        publication = self.service.finalize_and_commit(
            self.actor, self.project.id, self.stage.id, day1.draft_id,
            command_id=draft_command(7312), expected_revision=saved_day1.revision,
        )
        self.source.source_commit = publication.commit_id
        day2 = self.prepared_continuity_draft(
            setup=setup, command_index=7313, meeting_date='2026-11-04',
            baseline=report_api.PublicationRef(publication.manifest.publication_id, publication.manifest_sha256, publication.commit_id),
        )
        day2_note_id = day2.authoring_context['current_observations'][0]['note_id']
        with project_page(self.editor_url(day2.draft_id)) as page:
            page.wait_for_selector(f'[data-continuity-current-note-id="{day2_note_id}"] [data-report-wysiwyg-region]')
            observed = page.evaluate("""
                ([oldText, currentId]) => {
                    const oldNode = Array.from(document.querySelectorAll('[data-matrix-readonly-note]'))
                        .find(node => node.textContent.includes(oldText));
                    const oldCell = oldNode?.closest('td');
                    const current = document.querySelector(`[data-continuity-current-note-id="${currentId}"] [data-report-wysiwyg-region]`);
                    return {
                        oldVisible: Boolean(oldNode),
                        oldEditable: Boolean(oldNode?.closest('[data-report-wysiwyg-region]')),
                        oldFallbackTags: oldCell.querySelectorAll('.tag.is-light').length,
                        currentEditable: Boolean(current),
                    };
                }
            """, ['Day1 readonly blue note.', day2_note_id])
        self.assertEqual({'oldVisible': True, 'oldEditable': False, 'oldFallbackTags': 0, 'currentEditable': True}, observed)

    def test_shouldShowStatusTagOnlyForGenuinelyEmptyMatrixCell(self):
        draft = self.prepared_continuity_draft()
        with project_page(self.editor_url(draft.draft_id)) as page:
            page.wait_for_selector('[data-continuity-matrix]')
            invalid_fallbacks = page.evaluate("""
                () => Array.from(document.querySelectorAll('[data-continuity-matrix] td'))
                    .filter(cell => (cell.querySelector('[data-matrix-readonly-note]')
                        || cell.querySelector('[data-matrix-action-body]')
                        || cell.querySelector('[data-report-wysiwyg-region]'))
                        && cell.querySelector('.tag.is-light'))
                    .map(cell => cell.textContent.trim())
            """)

        self.assertEqual([], invalid_fallbacks)

    def test_shouldKeepEachHistoricalPrefixAndCurrentEmptyObservationPrefix(self):
        setup = self.continuity_setup(7350)
        day1 = self.finalized_daily_publication(setup=setup, command_index=7351, save_index=7352,
                                                finalize_index=7353, meeting_date='2026-11-03',
                                                text='Day1 exact prefix note.')
        self.source.source_commit = day1.commit_id
        day2 = self.finalized_daily_publication(
            setup=setup, command_index=7354, save_index=7355, finalize_index=7356,
            meeting_date='2026-11-04', text='Day2 exact prefix note.',
            baseline=report_api.PublicationRef(day1.manifest.publication_id, day1.manifest_sha256, day1.commit_id),
        )
        self.source.source_commit = day2.commit_id
        day3 = self.prepared_continuity_draft(
            setup=setup, command_index=7357, meeting_date='2026-11-05',
            baseline=report_api.PublicationRef(day2.manifest.publication_id, day2.manifest_sha256, day2.commit_id),
        )
        day3_note_id = day3.authoring_context['current_observations'][0]['note_id']
        with project_page(self.editor_url(day3.draft_id)) as page:
            page.wait_for_selector(f'[data-continuity-current-note-id="{day3_note_id}"] [data-report-wysiwyg-region]')
            observed = page.evaluate("""
                currentId => {
                    const prefixes = Array.from(document.querySelectorAll('[data-matrix-readonly-prefix]')).map(node => node.textContent);
                    const currentRoot = document.querySelector(`[data-continuity-current-note-id="${currentId}"]`).closest('td');
                    return {prefixes, currentPrefix: currentRoot.querySelector('[data-matrix-source-prefix]').textContent};
                }
            """, day3_note_id)
        self.assertIn('ww45.2(In Progress):', observed['prefixes'])
        self.assertIn('ww45.3(In Progress):', observed['prefixes'])
        self.assertEqual('ww45.4(In Progress):', observed['currentPrefix'])

    def test_shouldRenderReadonlyWeeklyPeriodFromExplicitPublications(self):
        setup = self.continuity_setup(7400)
        day1 = self.finalized_daily_publication(setup=setup, command_index=7410, save_index=7411,
                                                finalize_index=7412, meeting_date='2026-11-03',
                                                text='Day1 period note.')
        self.source.source_commit = day1.commit_id
        day2 = self.finalized_daily_publication(
            setup=setup, command_index=7413, save_index=7414, finalize_index=7415,
            meeting_date='2026-11-04', text='Day2 period note.',
            baseline=report_api.PublicationRef(day1.manifest.publication_id, day1.manifest_sha256, day1.commit_id),
        )
        url = (self.live_server_url + reverse('ui_web:report_period', kwargs={
            'project_id': self.project.id, 'stage_id': self.stage.id,
            'period_key': quote(day2.manifest.period_key, safe=''),
        }) + f'?publication_id={day1.manifest.publication_id}&publication_id={day2.manifest.publication_id}')
        with project_page(url) as page:
            page.wait_for_selector('[data-period-matrix]')
            observed = page.evaluate("""
                () => ({text: document.querySelector('[data-period-matrix]').textContent,
                        prefixes: Array.from(document.querySelectorAll('[data-period-source-prefix]')).map(node => node.textContent),
                        actionText: Array.from(document.querySelectorAll('[data-period-action-label], [data-period-action-body]')).map(node => node.textContent).join(' '),
                        editors: document.querySelectorAll('[data-report-wysiwyg-region]').length})
            """)
        self.assertIn('Day1 period note.', observed['text'])
        self.assertIn('Day2 period note.', observed['text'])
        self.assertIn('ww45.2(In Progress):', observed['prefixes'])
        self.assertIn('AR', observed['actionText'])
        self.assertIn('Retest fixed patch', observed['actionText'])
        self.assertEqual(0, observed['editors'])

    def test_shouldCreateAndFinalizeWeeklyDraftFromStageSelectionForm(self):
        first_setup = self.continuity_setup(7800)
        weekly_document = continuity_starter_document('weekly')
        weekly = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(7802),
            name='Weekly continuity',
            document=weekly_document,
            fill_policy=default_fill_policy(weekly_document),
        )
        first_day = self.finalized_daily_publication(setup=first_setup, command_index=7810, save_index=7811,
                                                     finalize_index=7812, meeting_date='2026-11-03',
                                                     text='First series day.')
        self.source.source_commit = first_day.commit_id
        second_setup = self.continuity_setup(7820)
        second_day1 = self.finalized_daily_publication(setup=second_setup, command_index=7822, save_index=7823,
                                                       finalize_index=7824, meeting_date='2026-11-03',
                                                       text='Second series day1.')
        self.source.source_commit = second_day1.commit_id
        second_day2 = self.finalized_daily_publication(
            setup=second_setup, command_index=7825, save_index=7826, finalize_index=7827,
            meeting_date='2026-11-04', text='Second series day2.',
            baseline=report_api.PublicationRef(second_day1.manifest.publication_id, second_day1.manifest_sha256, second_day1.commit_id),
        )
        stage_url = self.live_server_url + reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })
        weekly_choice = f'user|{weekly.template_id}|{weekly.revision}|{weekly.revision_hash}'

        with project_page(stage_url) as page:
            page.wait_for_selector('[data-report-weekly-form]')
            page.locator('[data-report-weekly-form] [name="series_id"]').select_option(second_setup['series'].series_id)
            page.locator('[data-report-weekly-form] [name="period_key"]').select_option(second_day2.manifest.period_key)
            page.locator('[data-report-weekly-form] [name="template_choice"]').select_option(weekly_choice)
            page.locator(f'[data-report-weekly-form] input[value="{second_day1.manifest.publication_id}"]').check()
            page.locator(f'[data-report-weekly-form] input[value="{second_day2.manifest.publication_id}"]').check()
            with page.expect_response('**/weekly-drafts/') as weekly_response:
                page.locator('[data-report-weekly-create]').click()
            self.assertEqual(302, weekly_response.value.status)
            page.wait_for_url('**/reports/drafts/*/')
            draft_id = page.url.rstrip('/').rsplit('/', 1)[-1]
            page.wait_for_selector('[data-continuity-matrix]')
            with page.expect_navigation():
                page.locator('[data-report-finalize-confirm]').check()
                page.locator('[data-report-finalize-button]').click()
            publication_id = page.url.rstrip('/').rsplit('/', 1)[-1]

        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        publication = self.service.get_publication(self.actor, self.project.id, self.stage.id, publication_id)

        self.assertEqual('weekly_view', draft.authoring_context['report_role'])
        self.assertEqual('weekly_view', publication.manifest.report_role)
        self.assertEqual(second_day2.manifest.period_key, publication.manifest.period_key)
        bad_response = self.client.post(reverse('ui_web:report_weekly_draft_create', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        }), {
            'command_id': draft_command(7828),
            'series_id': second_setup['series'].series_id,
            'period_key': second_day2.manifest.period_key,
            'template_choice': weekly_choice,
            'publication_id': [first_day.manifest.publication_id, second_day2.manifest.publication_id],
        }, **self.auth('alice'))
        self.assertNotEqual(302, bad_response.status_code)

    def test_shouldShowChineseB2LabelsAndStalePolicyError(self):
        setup = self.continuity_setup(7900)
        series = setup['series']
        self.continuity_service.save_series_policy(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(7902),
            series_id=series.series_id,
            expected_revision=series.revision,
            expected_revision_hash=series.revision_hash,
            name='Server newer name',
            calendar=series.calendar,
            template_selection=series.default_template_selection,
        )
        choice = (
            f'user|{series.default_template_selection.template_id}|'
            f'{series.default_template_selection.revision}|'
            f'{series.default_template_selection.revision_hash}'
        )
        self.client.cookies['django_language'] = 'zh-hans'
        response = self.client.post(reverse('ui_web:report_series_policy', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'series_id': series.series_id,
        }), {
            'command_id': draft_command(7903),
            'expected_revision': str(series.revision),
            'expected_revision_hash': series.revision_hash,
            'series_name': '用户未保存名称',
            'calendar_choice': 'iso8601',
            'timezone': 'Asia/Shanghai',
            'template_choice': choice,
        }, **self.auth('alice'))
        body = response.content.decode('utf-8')

        with project_page(self.editor_url(self.prepared_continuity_draft(setup=setup, command_index=7904).draft_id),
                          language='zh-hans') as page:
            text = page.text_content('body')

        self.assertEqual(409, response.status_code)
        self.assertIn('系列策略已变更', body)
        self.assertIn('用户未保存名称', body)
        self.assertIn('添加报告常驻备注', text)

    def test_shouldEnforceCalendarIdentityAndPreserveDateMapOnRename(self):
        setup = self.continuity_setup(8000)
        date_map = {
            '2026-11-03': {'workweek_year': 2026, 'workweek': 45, 'weekday': 2},
        }
        calendar = report_api.ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'date_map', date_map)
        series = self.continuity_service.create_series(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(8002),
            name='Date map series',
            calendar=calendar,
            template_selection=setup['template_selection'],
        )
        with self.assertRaises(report_api.ReportError):
            self.continuity_service.save_series_policy(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(8003),
                series_id=series.series_id,
                expected_revision=series.revision,
                expected_revision_hash=series.revision_hash,
                name='Bad timezone same identity',
                calendar=report_api.ReportingCalendar('intel-workweek', 7, 'UTC', 'date_map', date_map),
                template_selection=setup['template_selection'],
            )
        revised = self.continuity_service.save_series_policy(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(8004),
            series_id=series.series_id,
            expected_revision=series.revision,
            expected_revision_hash=series.revision_hash,
            name='New calendar revision',
            calendar=report_api.ReportingCalendar('intel-workweek', 8, 'UTC', 'date_map', date_map),
            template_selection=setup['template_selection'],
        )
        response = self.client.post(reverse('ui_web:report_series_policy', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'series_id': series.series_id,
        }), {
            'command_id': draft_command(8005),
            'expected_revision': str(revised.revision),
            'expected_revision_hash': revised.revision_hash,
            'series_name': 'Renamed date map',
            'calendar_choice': 'iso8601',
            'calendar_id': revised.calendar.calendar_id,
            'calendar_revision': str(revised.calendar.revision),
            'calendar_week_rule': revised.calendar.week_rule,
            'calendar_date_map': json.dumps(revised.calendar.date_map, ensure_ascii=False, separators=(',', ':')),
            'timezone': revised.calendar.timezone,
            'template_choice': (
                f'user|{revised.default_template_selection.template_id}|'
                f'{revised.default_template_selection.revision}|'
                f'{revised.default_template_selection.revision_hash}'
            ),
        }, **self.auth('alice'))
        saved = self.continuity_service.list_series(self.actor, self.project.id, self.stage.id).items[-1]
        page = self.client.get(reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        }), **self.auth('alice')).content.decode('utf-8')

        self.assertEqual(302, response.status_code)
        self.assertEqual('Renamed date map', saved.name)
        self.assertEqual('date_map', saved.calendar.week_rule)
        self.assertEqual(date_map, saved.calendar.date_map)
        self.assertIn('2026-11-03', page)
        self.assertIn('data-calendar-date-map-readonly', page)

    def test_shouldCreateLinkedCorrectionFromPublicationPage(self):
        setup = self.continuity_setup(7500)
        publication = self.finalized_daily_publication(setup=setup, command_index=7510, save_index=7511,
                                                       finalize_index=7512, meeting_date='2026-11-03',
                                                       text='Published correction seed.')
        with project_page(self.publication_url(publication.manifest.publication_id)) as page:
            page.wait_for_selector('[data-report-linked-revision]')
            with page.expect_navigation():
                page.locator('[data-report-linked-revision]').click()
            draft_id = page.url.rstrip('/').rsplit('/', 1)[-1]
            page.wait_for_selector('[data-continuity-matrix]')
            body = page.text_content('body')
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        self.assertEqual(publication.manifest.publication_id, draft.parent_publication_id)
        self.assertEqual(publication.manifest.publication_id, draft.authoring_context['base_daily_publication']['publication_id'])
        self.assertIn('Published correction seed.', body)

    def test_shouldApplyContinuityChangeThroughDraftService(self):
        draft = self.prepared_continuity_draft()
        persistent_id = '76000000-0000-4000-8000-000000000212'
        saved = self.service.save_authored(
            self.actor, self.project.id, self.stage.id, draft.draft_id,
            command_id=draft_command(7201), expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash, edits=(),
            continuity_changes=({'kind': 'add_persistent_note', 'note_id': persistent_id, 'target': 'issue',
                                 'issue_ref': draft.authoring_context['row_order']['rows'][0]['issue_ref'],
                                 'fragment': plain_fragment('Persistent service carry note.'),
                                 'carry_forward': True},),
        )
        self.assertEqual(persistent_id, saved.authoring_context['persistent_notes'][0]['note_id'])

    def publication_url(self, publication_id):
        return self.live_server_url + reverse('ui_web:report_publication', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'publication_id': publication_id,
        })


def plain_fragment(text, *, foreground=None):
    return {'schema_version': 2, 'blocks': [{
        'type': 'paragraph',
        'content': [{
            'type': 'text',
            'text': text,
            'marks': [],
            'foreground': foreground,
            'background': None,
        }],
    }]}
