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
        validation_script_path = project_root / 'scripts' / 'validate_ui_design_gate.ps1'

        contract = contract_path.read_text(encoding='utf-8')
        validation_script = validation_script_path.read_text(encoding='utf-8')
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
            'dashboard-tool-form',
            'dashboard-tool-grid',
            'dashboard-tool-field',
            'dashboard-tool-actions',
            'dashboard_editor_state_banners.html',
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
        self.assertIn('scripts\\validate_ui_design_gate.ps1', contract)
        self.assertIn('ui_web.tests.test_ui_design_baseline_gate', validation_script)
        self.assertIn('openspec validate standardize-dashboard-ui-design-system --strict', validation_script)
        self.assertIn('Invoke-Checked', validation_script)
        self.assertIn('$LASTEXITCODE', validation_script)
        for contract_name in expected_contracts:
            self.assertIn(contract_name, contract)
            self.assertIn(contract_name, implementation_surface)
        for path in [overlay_path, audit_path, docs_index_path, openspec_docs_index_path]:
            self.assertIn(
                'openspec/docs/current-baseline/ui-design-system.md',
                path.read_text(encoding='utf-8'),
                str(path),
            )

    def test_shouldUseToolFormContractForLightweightDashboardForms(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        tool_form_templates = [
            template_dir / 'ai_dashboard_workflow.html',
            template_dir / 'task_forecast.html',
            template_dir / 'partials' / 'bug_trend_content.html',
            template_dir / 'partials' / 'current_tasks_filters.html',
            template_dir / 'partials' / 'pull_request_filters.html',
        ]

        # Then
        for path in tool_form_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-tool-form', content, str(path))
            self.assertIn('dashboard-tool-grid', content, str(path))
            self.assertNotIn('data-dirty-form', content, str(path))
            self.assertNotIn('data-required-form', content, str(path))

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
        state_partial = (template_dir / 'partials' / 'dashboard_editor_state_banners.html').read_text(encoding='utf-8')
        self.assertIn('dashboard-unsaved-banner', state_partial)
        self.assertIn('dashboard-validation-banner', state_partial)
        for path in dirty_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-edit-form', content, str(path))
            self.assertIn('dashboard-action-bar', content, str(path))
            self.assertIn('partials/dashboard_editor_state_banners.html', content, str(path))
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
        self.assertIn('.dashboard-tool-form', css)
        self.assertIn('.dashboard-tool-grid', css)
        self.assertIn('.dashboard-tool-field', css)
        self.assertIn('.dashboard-tool-actions', css)
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
