from pathlib import Path

from django.test import SimpleTestCase


class TestDashboardUiDesignSystem(SimpleTestCase):
    def test_shouldKeepUiDesignSystemContractDocumentedAndReferenced(self):
        # Given
        project_root = Path(__file__).resolve().parents[2]
        contract_path = project_root / 'openspec' / 'docs' / 'current-baseline' / 'ui-design-system.md'
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        audit_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / '2026-09-08-ui-baseline-audit.md'
        docs_index_path = project_root / 'docs' / 'README.md'
        openspec_docs_index_path = project_root / 'openspec' / 'docs' / 'README.md'

        contract = contract_path.read_text(encoding='utf-8')
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        css = (Path(__file__).resolve().parents[1] / 'static' / 'css' / 'main.css').read_text(encoding='utf-8')
        script = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
        templates = '\n'.join(path.read_text(encoding='utf-8') for path in template_dir.rglob('*.html'))
        implementation_surface = f'{css}\n{script}\n{templates}'

        expected_contracts = [
            'dashboard-edit-form',
            'dashboard-form-grid',
            'dashboard-form-field',
            'dashboard-action-bar',
            'dashboard-action-group',
            'dashboard-required-tag',
            'dashboard-validation-banner',
            'dashboard-unsaved-banner',
            'provider-tab-shell',
            'provider-tab-list',
            'provider-tab-body',
            'scope-provider-choice',
            'provider-tab-check',
            'responsive-admin-table',
            'help-tip',
            'workbench-shell',
            'workbench-grid',
        ]

        # Then
        self.assertIn('Dashboard UI Design System Contract', contract)
        for contract_name in expected_contracts:
            self.assertIn(contract_name, contract)
            self.assertIn(contract_name, implementation_surface)
        for path in [overlay_path, audit_path, docs_index_path, openspec_docs_index_path]:
            self.assertIn(
                'openspec/docs/current-baseline/ui-design-system.md',
                path.read_text(encoding='utf-8'),
                str(path),
            )

    def test_shouldRequireSharedDesignSystemClassesForDirtyEditors(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        dirty_templates = [
            path
            for path in template_dir.rglob('*.html')
            if 'data-dirty-form' in path.read_text(encoding='utf-8')
        ]

        # Then
        self.assertGreaterEqual(len(dirty_templates), 2)
        for path in dirty_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-edit-form', content, str(path))
            self.assertIn('dashboard-action-bar', content, str(path))
            self.assertIn('dashboard-unsaved-banner', content, str(path))
            self.assertIn('data-required-form', content, str(path))
            self.assertIn('Cancel Editing', content, str(path))

    def test_shouldRequireSharedRequiredTagClassInSetupEditors(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        setup_templates = [
            template_dir / 'bug_trend_scope_config.html',
            template_dir / 'partials' / 'provider_profile_editor.html',
        ]

        # Then
        for path in setup_templates:
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('class="tag is-small is-danger', content, str(path))
            self.assertIn('dashboard-required-tag', content, str(path))

    def test_shouldDefineButtonTagAndEditorControlsThroughSharedCssContracts(self):
        # Given
        css_path = Path(__file__).resolve().parents[1] / 'static' / 'css' / 'main.css'
        css = css_path.read_text(encoding='utf-8')

        # Then
        self.assertIn('.dashboard-form-grid', css)
        self.assertIn('.dashboard-form-field', css)
        self.assertIn('.dashboard-action-bar', css)
        self.assertIn('.dashboard-action-group', css)
        self.assertIn('.dashboard-required-tag', css)
        self.assertIn('.is-missing-required', css)
        self.assertIn('.dashboard-required-message', css)
        self.assertIn('.dashboard-validation-banner', css)
        self.assertIn('.dashboard-unsaved-banner', css)
        self.assertNotIn(".button,\n.input,\n.textarea,\n.select select,\n.tag", css)

    def test_shouldDefineRequiredValidationBehaviorThroughSharedScript(self):
        # Given
        script_path = Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js'
        script = script_path.read_text(encoding='utf-8')

        # Then
        self.assertIn('function initializeRequiredForms()', script)
        self.assertIn('[data-required-form]', script)
        self.assertIn('data-required-message-for', script)
        self.assertIn('aria-invalid', script)
