from pathlib import Path

from django.test import override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_template_compilation import schema1_document
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.report_history_ui_support import ReportHistoryUiBrowserSupport
from ui_web.tests.test_report_template_browser import project_page


AXE_CORE = Path('ui_web/frontend/node_modules/axe-core/axe.min.js').resolve()


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='',
                   WHITENOISE_AUTOREFRESH=True)
class TestReportEditorAccessibilityBrowser(ReportHistoryUiBrowserSupport):
    def test_report_editor_hosts_and_runtime_nodes_have_distinct_accessible_semantics(self):
        draft = self.prepared_continuity_draft()
        with project_page(self.editor_url(draft.draft_id)) as page:
            page.set_default_timeout(15000)
            page.wait_for_selector('[data-report-authoring-initialized="true"]')

            current = page.locator('[data-continuity-current-note-id] [data-report-wysiwyg-region]').first
            current_surface = current.locator('[data-report-editor-surface]')
            self.assert_editor_surface(page, current_surface, 'Current day note')
            current.locator('.ProseMirror').fill('Accessible current note.')
            current.locator('.ProseMirror').press('Control+A')
            page.locator('[data-report-command="foreground"][data-color="#0055aa"]').click()
            self.assertIn('Accessible current note.', current.locator('.ProseMirror').inner_text())

            details = page.locator('[data-continuity-action-control]').first
            details.locator('summary').click()
            self.assert_editor_surface(page, details.locator('[data-continuity-action-editor]'), 'Resolution')
            details.locator('[data-continuity-action-editor] .ProseMirror').fill('Accessible resolution.')
            self.assertIn('Accessible resolution.', details.locator('[data-continuity-action-editor] .ProseMirror').inner_text())

            page.locator('[data-continuity-add-persistent][data-persistent-target="report"]').click()
            persistent = page.locator('[data-continuity-persistent-draft]').last
            self.assert_editor_surface(page, persistent.locator('[data-continuity-fragment-surface]'), 'Persistent note')
            persistent.locator('.ProseMirror').fill('Accessible persistent note.')
            self.assertIn('Accessible persistent note.', persistent.locator('.ProseMirror').inner_text())

            page.locator('[data-continuity-add-action]').first.click()
            action = page.locator('[data-new-report-action]').last
            self.assert_editor_surface(page, action.locator('.report-editor-surface'), 'AR')
            action.locator('.ProseMirror').fill('Accessible new action.')
            self.assertIn('Accessible new action.', action.locator('.ProseMirror').inner_text())

            page.evaluate("""
                async () => {
                    const { mount } = await import('/static/js/report_editor/adapter.js');
                    const label = document.createElement('span');
                    label.id = 'runtime-readonly-label';
                    label.textContent = 'Runtime readonly';
                    document.body.appendChild(label);
                    const host = document.createElement('div');
                    host.id = 'runtime-readonly-surface';
                    host.className = 'report-editor-surface paper';
                    host.tabIndex = 0;
                    host.setAttribute('role', 'group');
                    host.setAttribute('aria-labelledby', 'runtime-readonly-label');
                    document.body.appendChild(host);
                    window.__readonlyHandle = await mount(host, {
                        readOnly: true,
                        fragment: {
                            schema_version: 2,
                            blocks: [{
                                type: 'paragraph',
                                content: [{
                                    type: 'text',
                                    text: 'Read only runtime text.',
                                    marks: [],
                                    foreground: null,
                                    background: null,
                                }],
                            }],
                        },
                    });
                }
            """)
            readonly = self.editor_semantics(page.locator('#runtime-readonly-surface'))
            self.assertEqual('runtime-readonly-label', readonly['surfaceLabelledBy'])
            self.assertEqual('textbox', readonly['editorRole'])
            self.assertIsNone(readonly['editorName'])
            self.assertEqual('runtime-readonly-label', readonly['editorLabelledBy'])
            self.assertEqual('true', readonly['editorReadonly'])
            self.assertEqual('false', readonly['contentEditable'])

    def test_template_builder_editor_host_and_runtime_node_have_accessible_semantics(self):
        url = self.live_server_url + reverse('ui_web:report_templates', kwargs={'project_id': self.project.id})
        with project_page(url) as page:
            page.set_default_timeout(15000)
            page.get_by_text('Copy daily starter').click()
            page.wait_for_url('**/report-templates/*/')
            row = page.locator('[data-template-row]').first
            surface = row.locator('[data-template-editor-surface]')

            self.assert_editor_surface(page, surface, 'Rich text')
            row.locator('.ProseMirror').fill('Template editor stays accessible.')

            self.assertIn('Template editor stays accessible.', row.locator('.ProseMirror').inner_text())

    def test_fixed_template_content_is_static_readable_prose_not_readonly_widget(self):
        document = schema1_document()
        fixed = document['blocks'][0]
        fixed['fragment'] = {
            'schema_version': 2,
            'blocks': [
                {'type': 'heading', 'level': 2, 'content': [{
                    'type': 'text',
                    'text': 'Fixed Heading',
                    'marks': [],
                    'foreground': None,
                    'background': None,
                }]},
                {'type': 'paragraph', 'content': [{
                    'type': 'text',
                    'text': 'Fixed paragraph stays readable.',
                    'marks': [],
                    'foreground': None,
                    'background': None,
                }]},
            ],
        }
        template = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(9820),
            name='Fixed content accessibility',
            document=document,
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        draft = self.service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(9821),
            selection=report_api.ReportSelection(capture_id=self.archive.capture_id, timezone='Asia/Shanghai'),
            template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
        )

        with project_page(self.editor_url(draft.draft_id)) as page:
            page.set_default_timeout(15000)
            fixed_content = page.locator('[data-template-fixed-content]')
            fixed_content.wait_for()
            page.add_script_tag(path=str(AXE_CORE))
            state = fixed_content.evaluate("""
                (node) => {
                    const surface = node.querySelector('.report-editor-surface');
                    return {
                        text: surface?.innerText || '',
                        hasHeading: Boolean(surface?.querySelector('h1,h2,h3')?.textContent.includes('Fixed Heading')),
                        ariaReadonly: surface?.getAttribute('aria-readonly') || null,
                        role: surface?.getAttribute('role') || null,
                        contentEditable: surface?.getAttribute('contenteditable') || null,
                        hasTextbox: Boolean(surface?.querySelector('[role="textbox"], .ProseMirror')),
                    };
                }
            """)
            axe = page.evaluate("""
                async () => {
                    const result = await window.axe.run(
                        document.querySelector('[data-template-fixed-content]'),
                        { runOnly: { type: 'rule', values: ['aria-prohibited-attr'] } }
                    );
                    return result.violations.map(item => ({
                        id: item.id,
                        nodes: item.nodes.map(node => node.target.join(' ')),
                    }));
                }
            """)
            before = state['text']
            fixed_content.click()
            page.keyboard.type(' MUTATION')
            after = fixed_content.locator('.report-editor-surface').inner_text()

        self.assertEqual([], axe)
        self.assertTrue(state['hasHeading'], state)
        self.assertIn('Fixed paragraph stays readable.', state['text'])
        self.assertIsNone(state['ariaReadonly'], state)
        self.assertIsNone(state['role'], state)
        self.assertIsNone(state['contentEditable'], state)
        self.assertFalse(state['hasTextbox'], state)
        self.assertEqual(before, after)

    def assert_editor_surface(self, page, surface, expected_name):
        self.assertEqual(expected_name, surface.get_attribute('aria-label'))
        self.assertEqual('group', surface.get_attribute('role'))
        self.assertNotEqual('textbox', surface.get_attribute('role'))
        surface.click()
        surface.locator('.ProseMirror').wait_for()
        state = self.editor_semantics(surface)
        self.assertEqual('textbox', state['editorRole'], state)
        self.assertEqual(expected_name, state['editorName'], state)
        self.assertEqual('true', state['editorMultiline'], state)
        self.assertEqual('false', state['editorReadonly'], state)
        self.assertEqual('true', state['contentEditable'], state)
        page.wait_for_function(
            "(surface) => surface.querySelector('.ProseMirror')?.getAttribute('aria-label') === surface.getAttribute('aria-label')",
            arg=surface.element_handle(),
        )

    def editor_semantics(self, surface):
        return surface.evaluate("""
            (node) => {
                const editor = node.querySelector('.ProseMirror');
                return {
                    surfaceRole: node.getAttribute('role'),
                    surfaceName: node.getAttribute('aria-label'),
                    surfaceLabelledBy: node.getAttribute('aria-labelledby'),
                    editorRole: editor?.getAttribute('role') || null,
                    editorName: editor?.getAttribute('aria-label') || null,
                    editorLabelledBy: editor?.getAttribute('aria-labelledby') || null,
                    editorMultiline: editor?.getAttribute('aria-multiline') || null,
                    editorReadonly: editor?.getAttribute('aria-readonly') || null,
                    contentEditable: editor?.getAttribute('contenteditable') || null,
                    text: editor?.textContent || '',
                };
            }
        """)
