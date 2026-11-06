from pathlib import Path
import socket

from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes
from project_management.models import Project
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, draft_command
from project_management.tests.report_render_fixtures import source_key_hash
from project_management.tests.test_report_template_compilation import schema1_document
from ui_web.facades.project_reports import ProjectReportFacade
from ui_web.facades.report_templates import ProjectReportTemplateFacade
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_authoring_browser_support import (
    ReportAuthoringBrowserTestCase,
    browser_page,
    fetch_local_route_response,
    form_fields_from_request,
    fulfill_route_response,
    local_only_connect,
)


SCREENSHOT_DIR = Path('.tmp/authoring-main-20261103')
BUILDER_FIX_SCREENSHOT = SCREENSHOT_DIR / 'template-builder-fix2-desktop.png'
REPORT_FIX_SCREENSHOT = SCREENSHOT_DIR / 'template-report-fix2-contrast-desktop.png'


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportTemplateBrowser(ReportAuthoringBrowserTestCase):
    def setUp(self):
        super().setUp()
        Project.objects.create(
            id=self.project.id,
            owner_subject=self.actor.subject,
            key=self.project.key,
            name=self.project.name,
            archived=False,
        )
        self.template_service = report_api.ReportTemplateService(clock=FixedClock())
        self.service.template_service = self.template_service
        self.facade = None
        self._patch_template_facades()

    def template_library_url(self):
        return self.live_server_url + reverse('ui_web:report_templates', kwargs={'project_id': self.project.id})

    def stage_reports_url(self):
        return self.live_server_url + reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def report_facade(self):
        if self.facade is None:
            self.facade = ProjectReportFacade(
                ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
                self.service,
                self.archive,
                self.template_service,
            )
        return self.facade

    def template_facade(self):
        return ProjectReportTemplateFacade(
            ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            self.template_service,
        )

    def _patch_template_facades(self):
        from ui_web.views import project_reports, report_templates

        report_classes = (
            project_reports.ProjectStageReportView,
            project_reports.ReportDraftCreateView,
            project_reports.ReportDraftEditView,
            project_reports.ReportDraftSaveView,
            project_reports.ReportDraftFinalizeView,
            project_reports.ReportDraftRenderView,
            project_reports.ReportDraftDownloadView,
        )
        template_classes = (
            report_templates.ReportTemplateLibraryView,
            report_templates.ReportTemplateEditorView,
            report_templates.ReportTemplateSaveView,
            report_templates.ReportTemplateArchiveView,
            report_templates.ReportTemplateCopyView,
        )
        originals = [view.facade_factory for view in report_classes + template_classes]
        for view in report_classes:
            view.facade_factory = staticmethod(self.report_facade)
        for view in template_classes:
            view.facade_factory = staticmethod(self.template_facade)
        self.addCleanup(lambda: [setattr(view, 'facade_factory', original)
                                 for view, original in zip(report_classes + template_classes, originals)])

    def test_visualTemplateLibraryPinsReportSlotAndCompletionFlow(self):
        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            page.get_by_text('Add content').click()
            new_content = page.locator('[data-template-row]').last
            new_content.locator('[data-template-rich-panel] [data-template-editor-surface]').click()
            new_content.locator('[data-template-rich-panel] .ProseMirror').wait_for()
            page.keyboard.type('Browser fixed template text')
            slot_row = page.locator('[data-template-row][data-kind="slot"]').first
            slot_row.locator('[data-template-slot-fill-mode]').select_option('ai_optional')
            slot_row.locator('[data-template-slot-instruction]').fill('Use accepted source evidence.')
            with page.expect_navigation():
                page.locator('[data-template-save-button]').click()
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(BUILDER_FIX_SCREENSHOT), full_page=True)

        ready = self.template_service.list(self.actor, self.project.id, limit=20, offset=0).items[0]
        with project_page(self.stage_reports_url()) as page:
            page.locator('[name="template_choice"]').select_option(
                f'user|{ready.template_id}|{ready.current_revision}|{ready.revision_hash}'
            )
            with page.expect_navigation():
                page.get_by_text('Create draft').click()
            page.wait_for_selector('[data-report-wysiwyg-region]')
            page.wait_for_selector('[data-report-authoring-initialized="true"]')
            page.locator('[data-template-slot-id]').first.wait_for()
            slot = page.locator('[data-template-slot-id] [data-report-wysiwyg-region]').first
            slot.locator('[data-report-editor-surface]').click()
            slot.locator('.ProseMirror').wait_for()
            slot.locator('.ProseMirror').click()
            page.keyboard.type('#ALPHA-1')
            page.locator('.report-completion-option').nth(1).click()
            page.keyboard.press('Control+A')
            page.keyboard.type('Colored slot answer')
            page.keyboard.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            page.locator('[data-report-save-button]').click()
            page.wait_for_load_state('domcontentloaded')
            page.locator('[data-report-wysiwyg-region][data-existing="true"]').first.wait_for()
            inline = page.evaluate("""
                () => {
                    const root = document.querySelector('[data-report-editor]');
                    const slotTitle = document.querySelector('[data-template-slot-id] .title');
                    const header = document.querySelector('.report-readonly-data th');
                    const bodyCell = Array.from(document.querySelectorAll('.report-readonly-data td'))
                        .find(cell => cell.textContent.includes('DEMO-101'));
                    const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number).map(v => {
                        v /= 255;
                        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                    });
                    const contrast = (a, b) => {
                        const la = 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
                        const lb = 0.2126 * b[0] + 0.7152 * b[1] + 0.0722 * b[2];
                        return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
                    };
                    return {
                        text: root.textContent,
                        slotColor: getComputedStyle(slotTitle).color,
                        slotBackground: getComputedStyle(slotTitle.closest('.report-section-band')).backgroundColor,
                        headerColor: getComputedStyle(header).color,
                        headerBackground: getComputedStyle(header).backgroundColor,
                        headerContrast: contrast(rgb(getComputedStyle(header).color), rgb(getComputedStyle(header).backgroundColor)),
                        bodyText: bodyCell.textContent,
                        bodyColor: getComputedStyle(bodyCell).color,
                        bodyBackground: getComputedStyle(bodyCell).backgroundColor,
                        bodyContrast: contrast(rgb(getComputedStyle(bodyCell).color), rgb(getComputedStyle(bodyCell).backgroundColor)),
                    };
                }
            """)
            page.screenshot(path=str(REPORT_FIX_SCREENSHOT), full_page=True)
            old_url = page.url
            draft_id = old_url.rstrip('/').rsplit('/', 1)[-1]
            html_before = self.service.render(self.actor, self.project.id, self.stage.id, draft_id, revision=2).html_document

        template = self.template_service.get(self.actor, self.project.id, str(ready.template_id), revision=ready.current_revision)
        self.template_service.save(
            self.actor,
            self.project.id,
            str(template.template_id),
            command_id=draft_command(940),
            expected_revision=template.revision,
            expected_revision_hash=template.revision_hash,
            name='Daily starter v2',
            document={**template.document, 'blocks': template.document['blocks'][:-1]},
            fill_policy=template.fill_policy,
        )
        publication = self.service.finalize_and_commit(
            self.actor,
            self.project.id,
            self.stage.id,
            draft_id,
            command_id=draft_command(941),
            expected_revision=2,
        )
        files = self.archive.repository.list_files(f'report_publications/{publication.manifest.publication_id}')
        html_after = self.service.read_artifact(
            self.actor,
            self.project.id,
            self.stage.id,
            publication.manifest.publication_id,
            'html',
        )

        self.assertIn(b'Browser fixed template text', html_before)
        self.assertIn(b'Colored slot answer', html_before)
        self.assertIn('DEMO-101', inline['text'])
        self.assertIn('In Progress', inline['text'])
        self.assertIn('Retest fixed patch', inline['text'])
        self.assertIn('Evidence and coverage', inline['text'])
        self.assertEqual('rgb(17, 24, 39)', inline['slotColor'])
        self.assertEqual('rgb(251, 252, 254)', inline['slotBackground'])
        self.assertGreaterEqual(inline['headerContrast'], 4.5, inline)
        self.assertIn('DEMO-101', inline['bodyText'])
        self.assertGreaterEqual(inline['bodyContrast'], 4.5, inline)
        self.assertEqual(6, len(files))
        self.assertEqual(html_before, html_after)

    def test_builderKindSwitchMountFailureAndDirtyGuards(self):
        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            row = page.locator('[data-template-row]').first
            row.locator('[data-template-editor-surface]').click()
            row.locator('.ProseMirror').wait_for()
            row.locator('.ProseMirror').click()
            page.keyboard.type('Kind switch keeps paint')
            page.keyboard.press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            row.locator('[data-template-kind]').select_option('slot')
            row.locator('[data-template-slot-label]').fill('Switched slot')
            with page.expect_navigation():
                page.locator('[data-template-save-button]').click()

        saved = self.template_service.list(self.actor, self.project.id, limit=20, offset=0).items[0]
        revision = self.template_service.get(self.actor, self.project.id, str(saved.template_id), revision=saved.current_revision)
        slot = next(block for block in revision.document['blocks'] if block['kind'] == 'slot' and block['label'] == 'Switched slot')
        text_run = slot['initial']['blocks'][0]['content'][0]

        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            page.evaluate("window.ReportMilkdownEditor.createRuntime = null")
            page.locator('[data-template-row] [data-template-editor-surface]').first.click()
            page.wait_for_function("document.querySelector('[data-template-builder]').dataset.templateMountFailed === 'true'")
            disabled = page.locator('[data-template-save-button]').is_disabled()
            page.evaluate("""
                () => {
                    window.__confirmText = null;
                    window.confirm = text => { window.__confirmText = text; return false; };
                    const link = document.querySelector('nav.breadcrumb a[href]');
                    const event = new MouseEvent('click', {bubbles: true, cancelable: true});
                    link.dispatchEvent(event);
                    window.__blocked = event.defaultPrevented;
                }
            """)
            blocked = page.evaluate("({blocked: window.__blocked, text: window.__confirmText})")

        self.assertIn('Kind switch keeps paint', text_run['text'])
        self.assertEqual('#0055aa', text_run['foreground'])
        self.assertTrue(disabled)
        self.assertTrue(blocked['blocked'])
        self.assertIn('Unsaved template edits', blocked['text'])

    def test_chineseDynamicRowSaveFailureDirtyGuardAndPendingMountRemoval(self):
        with project_page(self.template_library_url(), language='zh-hans') as page:
            page.get_by_text('复制每日起始模板').click()
            page.wait_for_url('**/report-templates/*/')
            page.locator('[data-template-add="slot"]').click()
            new_row = page.locator('[data-template-row]').last
            self.assertIn('填写槽标签', new_row.text_content())
            self.assertIn('必填', new_row.text_content())

            page.route('**/save/', lambda route: route.abort())
            page.locator('[data-template-save-button]').click()
            page.wait_for_function("document.querySelector('[data-template-status]').textContent.includes('模板保存失败')")

            page.evaluate("""
                () => {
                    window.__confirmText = null;
                    window.confirm = text => { window.__confirmText = text; return false; };
                    const form = document.querySelector('form[action="/projects/language/"]');
                    const event = new Event('submit', {bubbles: true, cancelable: true});
                    form.dispatchEvent(event);
                    window.__languageBlocked = event.defaultPrevented;
                }
            """)
            guard = page.evaluate("({blocked: window.__languageBlocked, text: window.__confirmText})")

        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            page.evaluate("""
                () => {
                    window.__destroyedRuntime = 0;
                    window.__resolveRuntime = null;
                    window.ReportMilkdownEditor.createRuntime = async (element, fragment) => {
                        return await new Promise(resolve => {
                            window.__resolveRuntime = () => resolve({
                                getFragment: () => fragment,
                                replaceFragment: () => {},
                                command: () => true,
                                destroy: () => { window.__destroyedRuntime += 1; },
                            });
                        });
                    };
                }
            """)
            row = page.locator('[data-template-row]').first
            row.locator('[data-template-editor-surface]').click()
            row.locator('[data-template-row-command="remove"]').click()
            page.evaluate("window.__resolveRuntime()")
            page.wait_for_function("window.__destroyedRuntime === 1")
            lifecycle = page.evaluate("""
                () => ({
                    destroyed: window.__destroyedRuntime,
                    mountFailed: document.querySelector('[data-template-builder]').dataset.templateMountFailed || '',
                })
            """)

        self.assertTrue(guard['blocked'])
        self.assertIn('未保存的模板编辑', guard['text'])
        self.assertEqual({'destroyed': 1, 'mountFailed': ''}, lifecycle)

    def test_delayedAcceptedSavePreservesNewerLocalEdits(self):
        held = {}

        def hold_first_save(route):
            held['route'] = route

        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            row = page.locator('[data-template-row]').first
            row.locator('[data-template-editor-surface]').click()
            row.locator('.ProseMirror').wait_for()
            row.locator('.ProseMirror').click()
            page.keyboard.type(' accepted A')
            page.route('**/save/', hold_first_save)
            page.locator('[data-template-save-button]').click()
            page.wait_for_function("document.querySelector('[data-template-save-button]').disabled === true")
            row.locator('.ProseMirror').click()
            page.keyboard.type(' newer B')
            fulfill_route_response(held['route'], fetch_local_route_response(held['route']))
            page.wait_for_function("document.querySelector('[data-template-status]').textContent.includes('Unsaved')")
            state = page.evaluate("""
                () => ({
                    url: location.href,
                    text: document.querySelector('.ProseMirror').textContent,
                    dirty: document.querySelector('[data-template-builder]').dataset.templateDirty,
                    revision: document.querySelector('[name="expected_revision"]').value,
                    command: document.querySelector('[name="command_id"]').value,
                })
            """)

        self.assertIn('/report-templates/', state['url'])
        self.assertIn('accepted A newer B', state['text'])
        self.assertEqual('true', state['dirty'])
        self.assertEqual('2', state['revision'])
        self.assertNotEqual(draft_command(0), state['command'])

    def test_lostResponseRetriesOriginalBodyAndKeepsNewerLocalEditDirty(self):
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

        with project_page(self.template_library_url()) as page:
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            row = page.locator('[data-template-row]').first
            row.locator('[data-template-editor-surface]').click()
            row.locator('.ProseMirror').wait_for()
            row.locator('.ProseMirror').click()
            page.keyboard.type(' original A')
            page.route('**/save/', lost_first_then_replay)
            page.locator('[data-template-save-button]').click()
            page.wait_for_function("document.querySelector('[data-template-status]').textContent.includes('失败') || document.querySelector('[data-template-status]').textContent.includes('failed')")
            row.locator('.ProseMirror').click()
            page.keyboard.type(' local B')
            page.locator('[data-template-save-button]').click()
            page.wait_for_function("document.querySelector('[name=\"expected_revision\"]').value === '2'")
            state = page.evaluate("""
                () => ({
                    text: document.querySelector('.ProseMirror').textContent,
                    dirty: document.querySelector('[data-template-builder]').dataset.templateDirty,
                    status: document.querySelector('[data-template-status]').textContent,
                })
            """)

        self.assertEqual(2, len(posts))
        self.assertEqual(posts[0]['command_id'], posts[1]['command_id'])
        self.assertEqual(posts[0]['document'], posts[1]['document'])
        self.assertIn('original A local B', state['text'])
        self.assertEqual('true', state['dirty'])
        self.assertIn('Unsaved', state['status'])

    def test_readonlyRegisterCssDoesNotOverrideAuthoredPaintDescendants(self):
        template = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(950),
            name='Paint template',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        draft = self.service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(951),
            selection=report_api.ReportSelection(capture_id=self.archive.capture_id, timezone='Asia/Shanghai'),
            template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
        )
        row = draft.snapshot.rows[0]
        target = {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'what'}
        paint = painted_register_fragment()
        saved = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(952),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '99000000-0000-4000-8000-000000000001',
                'narrative_override',
                target,
                paint,
                expected_original_hash=report_api.text_hash(row.what),
            ),),
        )

        with browser_page(self.editor_url(draft.draft_id)) as page:
            page.wait_for_selector('.report-readonly-data')
            observed = page.evaluate("""
                () => {
                    const blue = Array.from(document.querySelectorAll('.report-readonly-data *'))
                        .find(node => node.textContent === 'PAINT-LINK-BLUE');
                    const green = Array.from(document.querySelectorAll('.report-readonly-data *'))
                        .find(node => node.textContent === 'PAINT-LINK-GREEN');
                    const table = Array.from(document.querySelectorAll('.report-readonly-data span'))
                        .find(node => node.textContent === 'PAINT-TABLE-HIGHLIGHT');
                    return {
                        blueTag: blue.tagName,
                        blueParent: blue.parentElement.tagName,
                        blueColor: getComputedStyle(blue).color,
                        blueBackground: getComputedStyle(blue).backgroundColor,
                        blueWeight: getComputedStyle(blue).fontWeight,
                        greenColor: getComputedStyle(green).color,
                        greenStyle: getComputedStyle(green).fontStyle,
                        tableColor: getComputedStyle(table).color,
                        tableBackground: getComputedStyle(table).backgroundColor,
                        tableText: table.textContent,
                    };
                }
            """)
        reopened = self.service.get(self.actor, self.project.id, self.stage.id, draft.draft_id)

        self.assertEqual(saved.revision, 2)
        self.assertEqual(canonical_bytes(paint), canonical_bytes(reopened.authored_edits[0].fragment))
        self.assertEqual('A', observed['blueParent'])
        self.assertEqual('rgb(0, 85, 170)', observed['blueColor'])
        self.assertEqual('rgb(255, 244, 204)', observed['blueBackground'])
        self.assertIn(observed['blueWeight'], {'700', 'bold'})
        self.assertEqual('rgb(0, 128, 0)', observed['greenColor'])
        self.assertEqual('italic', observed['greenStyle'])
        self.assertEqual('rgb(170, 0, 0)', observed['tableColor'])
        self.assertEqual('rgb(223, 247, 232)', observed['tableBackground'])
        self.assertEqual('PAINT-TABLE-HIGHLIGHT', observed['tableText'])


class ProjectPage:
    def __init__(self, url, language=None):
        self.url = url
        self.language = language

    def __enter__(self):
        self.original_connect = socket.socket.connect
        socket.socket.connect = local_only_connect
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True, channel='chrome')
        self.context = self.browser.new_context(
            http_credentials={'username': 'alice', 'password': 'wonder'},
            viewport={'width': 1440, 'height': 1000},
        )
        if self.language:
            self.context.add_cookies([{'name': 'django_language', 'value': self.language, 'url': self.url}])
        self.page = self.context.new_page()
        self.page.route('**/*', lambda route: route.continue_()
                        if route.request.url.startswith(('http://127.0.0.1:', 'http://localhost:', 'data:', 'blob:'))
                        else route.abort())
        self.page.goto(self.url, wait_until='domcontentloaded')
        return self.page

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.browser.close()
            self.playwright.stop()
        finally:
            socket.socket.connect = self.original_connect


def project_page(url, language=None):
    return ProjectPage(url, language)


def painted_register_fragment():
    return {
        'schema_version': 2,
        'blocks': [
            {'type': 'paragraph', 'content': [{
                'type': 'link',
                'href': 'https://tracker.example.test/jira/browse/ALPHA-1',
                'content': [
                    {'type': 'text', 'text': 'PAINT-LINK-BLUE', 'marks': ['strong'], 'foreground': '#0055aa', 'background': '#fff4cc'},
                    {'type': 'text', 'text': 'PAINT-LINK-GREEN', 'marks': ['em'], 'foreground': '#008000', 'background': None},
                ],
            }]},
            {'type': 'table', 'headers': [[
                {'type': 'text', 'text': 'Paint header', 'marks': [], 'foreground': None, 'background': None},
            ]], 'rows': [[[
                {'type': 'text', 'text': 'PAINT-TABLE-HIGHLIGHT', 'marks': [], 'foreground': '#aa0000', 'background': '#dff7e8'},
            ]]]},
        ],
    }
