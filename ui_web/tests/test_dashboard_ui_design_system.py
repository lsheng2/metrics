import json
import re
from pathlib import Path

from django.test import SimpleTestCase


class TestDashboardUiDesignSystem(SimpleTestCase):
    def test_shouldKeepUiDesignSystemContractDocumentedAndReferenced(self):
        # Given
        project_root = Path(__file__).resolve().parents[2]
        contract_path = project_root / 'openspec' / 'docs' / 'current-baseline' / 'ui-design-system.md'
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        audit_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / '2026-09-08-ui-baseline-audit.md'
        polish_backlog_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / '2026-09-09-ui-polish-backlog.md'
        checklist_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / 'ui-change-checklist.md'
        gate_report_json_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / 'ui-gate-report.json'
        gate_report_md_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / 'ui-gate-report.md'
        monkey_e2e_checklist_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / 'provider-profile-scope-monkey-e2e-checklist.md'
        docs_index_path = project_root / 'docs' / 'README.md'
        openspec_docs_index_path = project_root / 'openspec' / 'docs' / 'README.md'
        validation_script_path = project_root / 'scripts' / 'validate_ui_design_gate.ps1'
        visual_manifest_script_path = project_root / 'scripts' / 'validate_ui_visual_manifest.ps1'
        live_route_script_path = project_root / 'scripts' / 'validate_ui_live_routes.ps1'
        full_manifest_script_path = project_root / 'scripts' / 'validate_ui_full_manifest_gate.ps1'
        report_refresh_script_path = project_root / 'scripts' / 'refresh_ui_gate_report.ps1'
        hook_script_path = project_root / 'scripts' / 'ui_design_fixture_hooks.py'

        contract = contract_path.read_text(encoding='utf-8')
        validation_script = validation_script_path.read_text(encoding='utf-8')
        visual_manifest_script = visual_manifest_script_path.read_text(encoding='utf-8')
        live_route_script = live_route_script_path.read_text(encoding='utf-8')
        full_manifest_script = full_manifest_script_path.read_text(encoding='utf-8')
        report_refresh_script = report_refresh_script_path.read_text(encoding='utf-8')
        hook_script = hook_script_path.read_text(encoding='utf-8')
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
            'dashboard-action-form',
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
            'dashboard-dense-table',
            'help-tip',
            'workbench-shell',
            'workbench-grid',
        ]

        # Then
        self.assertIn('Dashboard UI Design System Contract', contract)
        self.assertIn('scripts\\validate_ui_design_gate.ps1', contract)
        self.assertIn('scripts\\validate_ui_visual_manifest.ps1', contract)
        self.assertIn('ui_web.tests.test_ui_design_baseline_gate', validation_script)
        self.assertIn('openspec validate standardize-dashboard-ui-design-system --strict', validation_script)
        self.assertIn('audit_project_ui.py', validation_script)
        self.assertIn('audit_table_metrics.py', validation_script)
        self.assertIn('audit_layout_metrics.py', validation_script)
        self.assertIn('generate_ui_checklist.py', contract)
        self.assertIn('render_component_catalog.py', validation_script)
        self.assertIn('create_visual_regression_manifest.py', validation_script)
        self.assertIn('test_shouldRunVisualRegressionManifestAgainstCoreRoutes', visual_manifest_script)
        self.assertIn('run_visual_state_scenarios.py', live_route_script)
        self.assertIn('audit_layout_metrics.py', live_route_script)
        self.assertIn('refresh_ui_gate_report.ps1', validation_script)
        self.assertIn('validate_ui_live_routes.ps1', full_manifest_script)
        self.assertIn('-IncludeHooked', full_manifest_script)
        self.assertIn('run_visual_state_scenarios.py', full_manifest_script)
        self.assertIn('--include-hooked', full_manifest_script)
        self.assertIn('refresh_ui_gate_report.ps1', full_manifest_script)
        self.assertIn('create_ui_gate_report.py', report_refresh_script)
        self.assertIn('--include-hooked', report_refresh_script)
        self.assertIn('ui_design_fixture_hooks.py', live_route_script)
        self.assertIn('--project-root .', live_route_script)
        self.assertIn('--baseline-dir', live_route_script)
        self.assertIn('/provider-setup/', live_route_script)
        self.assertIn('/bug-trend/scope-config/', live_route_script)
        self.assertIn('Invoke-Checked', validation_script)
        self.assertIn('$LASTEXITCODE', validation_script)
        for contract_name in expected_contracts:
            self.assertIn(contract_name, contract)
            self.assertIn(contract_name, implementation_surface)
        self.assertIn('Compact Dashboard Review', polish_backlog_path.read_text(encoding='utf-8'))
        self.assertIn('Monkey-User Flow Review', polish_backlog_path.read_text(encoding='utf-8'))
        self.assertIn('Before Editing', checklist_path.read_text(encoding='utf-8'))
        self.assertIn('audit_layout_metrics.py', checklist_path.read_text(encoding='utf-8'))
        self.assertIn('run_visual_state_scenarios.py', checklist_path.read_text(encoding='utf-8'))
        self.assertIn('UI Gate Report', gate_report_md_path.read_text(encoding='utf-8'))
        self.assertEqual('passed', json.loads(gate_report_json_path.read_text(encoding='utf-8'))['status'])
        monkey_e2e_checklist = monkey_e2e_checklist_path.read_text(encoding='utf-8')
        self.assertIn('Provider/Profile/Scope Monkey-User E2E Checklist', monkey_e2e_checklist)
        self.assertIn('New Profile', monkey_e2e_checklist)
        self.assertIn('Test Connection', monkey_e2e_checklist)
        self.assertIn('Metadata To Dashboard Mapping', monkey_e2e_checklist)
        self.assertIn('provider_profile_test_success', hook_script)
        self.assertIn('provider_profile_test_failure', hook_script)
        self.assertIn('current_tasks_fake_data', hook_script)
        self.assertIn('pull_request_filter_applied', hook_script)
        self.assertIn('task_forecast_fake_data', hook_script)
        self.assertIn('team_velocity_fake_data', hook_script)
        self.assertIn('dev_velocity_fake_data', hook_script)
        self.assertIn('bug_trend_evidence_fake_data', hook_script)
        for path in [overlay_path, audit_path, polish_backlog_path, docs_index_path, openspec_docs_index_path]:
            self.assertIn(
                'openspec/docs/current-baseline/ui-design-system.md',
                path.read_text(encoding='utf-8'),
                str(path),
            )

    def test_shouldDocumentAutonomousUiAuditAndComponentTokenProfile(self):
        # Given
        project_root = Path(__file__).resolve().parents[2]
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        overlay = overlay_path.read_text(encoding='utf-8')

        # Then
        self.assertIn('## Component Token Profile', overlay)
        self.assertIn('dashboard-admin-v1.json', overlay)
        self.assertIn('compactDashboard', overlay)
        self.assertIn('## Autonomous Audit Scope', overlay)
        self.assertIn('## Audit Exceptions / Allowlist', overlay)
        self.assertIn('lsheng2-ui-design-audit-exceptions', overlay)
        self.assertIn('tableContractAllowlist', overlay)
        self.assertIn('tableMetricsAllowlist', overlay)
        self.assertIn('layoutMetricsAllowlist', overlay)
        self.assertIn('"buttonMetrics"', overlay)
        self.assertIn('"formMetrics"', overlay)
        self.assertIn('"layoutSelectors"', overlay)
        self.assertIn('Adapter status: reserved for future React/Next/Tailwind/component-tree projects', overlay)
        self.assertIn('validate_ui_full_manifest_gate.ps1', overlay)
        self.assertIn('refresh_ui_gate_report.ps1', overlay)
        self.assertIn('provider-profile-scope-monkey-e2e-checklist.md', overlay)
        self.assertIn('audit_project_ui.py', overlay)
        self.assertIn('audit_layout_metrics.py', overlay)
        self.assertIn('generate_ui_checklist.py', overlay)
        self.assertIn('lsheng2-ui-design-state-scenarios', overlay)
        self.assertIn('lsheng2-ui-design-hook-modules', overlay)
        self.assertIn('scripts/ui_design_fixture_hooks.py', overlay)
        self.assertIn('profile-required-missing', overlay)
        self.assertIn('scope-required-missing', overlay)
        self.assertIn('requiresHook', overlay)
        self.assertIn('provider_profile_test_success', overlay)
        self.assertIn('current_tasks_fake_data', overlay)
        self.assertIn('pull_request_filter_applied', overlay)
        self.assertIn('task_forecast_fake_data', overlay)
        self.assertIn('bug_trend_evidence_fake_data', overlay)
        self.assertIn('shared tokens/classes/partials first', overlay)

    def test_shouldKeepLocalComponentCatalogAndVisualManifestAvailable(self):
        # Given
        project_root = Path(__file__).resolve().parents[2]
        catalog_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'component-catalog' / 'dashboard-admin-v1.html'
        manifest_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'visual-regression' / 'manifest.json'
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        ci_dir = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'ci'

        catalog = catalog_path.read_text(encoding='utf-8')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        overlay = overlay_path.read_text(encoding='utf-8')
        pre_push = (ci_dir / 'pre-push.sample').read_text(encoding='utf-8')
        actions = (ci_dir / 'github-actions-ui-gate.sample.yml').read_text(encoding='utf-8')
        live_note = (ci_dir / 'live-route-gate.md').read_text(encoding='utf-8')

        # Then
        self.assertIn('Dashboard Admin Component Catalog', catalog)
        self.assertIn('dashboard-admin-v1', catalog)
        self.assertIn('<strong>Action:</strong>', catalog)
        self.assertIn('data-ui-action-group', catalog)
        self.assertIn('data-ui-form', catalog)
        self.assertEqual('lsheng2-ui-design', manifest['owner'])
        self.assertEqual(['scripts/ui_design_fixture_hooks.py'], manifest['hookModules'])
        self.assertGreaterEqual(len(manifest['viewports']), 3)
        self.assertIn('/provider-setup/', {item['route'] for item in manifest['capturePlan']})
        self.assertTrue({
            '/team-velocity/',
            '/dev-velocity/',
        }.issubset({item['route'] for item in manifest['capturePlan']}))
        velocity_captures = [
            item
            for item in manifest['capturePlan']
            if item['route'] in {'/team-velocity/', '/dev-velocity/'}
        ]
        self.assertTrue(all('chart-drilldown-selected' in item['stateTargets'] for item in velocity_captures))
        self.assertTrue(all('table-density' in item['stateTargets'] for item in velocity_captures))
        provider_capture = next(item for item in manifest['capturePlan'] if item['route'] == '/provider-setup/')
        scope_capture = next(item for item in manifest['capturePlan'] if item['route'] == '/bug-trend/scope-config/')
        current_tasks_capture = next(item for item in manifest['capturePlan'] if item['route'] == '/current-tasks/')
        evidence_capture = next(item for item in manifest['capturePlan'] if item['route'] == '/partials/bug-trend/evidence/')
        provider_scenarios = {item['name']: item for item in provider_capture['stateScenarios']}
        scope_scenarios = {item['name']: item for item in scope_capture['stateScenarios']}
        self.assertIn('profile-required-missing', provider_scenarios)
        self.assertIn('profile-dirty-unsaved', provider_scenarios)
        self.assertIn('scope-required-missing', scope_scenarios)
        self.assertIn('scope-dirty-unsaved', scope_scenarios)
        self.assertIn('required-summary-visible', provider_scenarios['profile-required-missing']['checks'])
        self.assertIn('dirty-banner-visible', scope_scenarios['scope-dirty-unsaved']['checks'])
        self.assertTrue(any(item.get('requiresHook') for item in provider_capture['stateScenarios']))
        self.assertEqual('provider_profile_test_success', provider_scenarios['profile-test-success']['hook'])
        self.assertEqual('provider_profile_test_failure', provider_scenarios['profile-test-failure']['hook'])
        self.assertIn('status-feedback-visible', provider_scenarios['profile-test-success']['checks'])
        self.assertIn('status-feedback-visible', provider_scenarios['profile-test-failure']['checks'])
        self.assertEqual('current_tasks_fake_data', current_tasks_capture['stateScenarios'][0]['hook'])
        self.assertEqual('bug_trend_evidence_fake_data', evidence_capture['stateScenarios'][0]['hook'])
        self.assertIn('component-catalog/dashboard-admin-v1.html', overlay)
        self.assertIn('visual-regression/manifest.json', overlay)
        self.assertIn('validate_ui_design_gate.ps1 -Broad', pre_push)
        self.assertIn('windows-latest', actions)
        self.assertIn('validate_ui_live_routes.ps1', live_note)
        self.assertIn('-IncludeHooked', live_note)
        self.assertIn('create_ui_gate_report.py', live_note)

    def test_shouldProvideLocalVisualStateFixtureHooks(self):
        # Given
        from scripts import ui_design_fixture_hooks

        hook_names = [
            'provider_profile_test_success',
            'provider_profile_test_failure',
            'current_tasks_fake_data',
            'pull_request_filter_applied',
            'task_forecast_fake_data',
            'team_velocity_fake_data',
            'dev_velocity_fake_data',
            'bug_trend_evidence_fake_data',
        ]

        # Then
        for hook_name in hook_names:
            payload = getattr(ui_design_fixture_hooks, hook_name)({})
            html = payload['html']
            self.assertIn('<style>', html, hook_name)
            self.assertIn('fixture', payload)
            self.assertNotIn('secret-', html, hook_name)
        self.assertIn('provider-connection-test-result', ui_design_fixture_hooks.provider_profile_test_success({})['html'])
        self.assertIn('dashboard-dense-table', ui_design_fixture_hooks.pull_request_filter_applied({})['html'])
        self.assertIn('dashboard-dense-table', ui_design_fixture_hooks.current_tasks_fake_data({})['html'])
        self.assertIn('dashboard-dense-table', ui_design_fixture_hooks.task_forecast_fake_data({})['html'])
        self.assertIn('dashboard-dense-table', ui_design_fixture_hooks.team_velocity_fake_data({})['html'])
        self.assertIn('dashboard-dense-table', ui_design_fixture_hooks.bug_trend_evidence_fake_data({})['html'])

    def test_shouldGiveEveryVisibleFormASharedUiContract(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        shared_form_classes = (
            'dashboard-edit-form',
            'dashboard-tool-form',
            'dashboard-action-form',
        )

        # Then
        for path in template_dir.rglob('*.html'):
            content = path.read_text(encoding='utf-8')
            for match in re.finditer(r'<form\b[^>]*>', content):
                form_tag = match.group(0)
                self.assertTrue(
                    any(shared_class in form_tag for shared_class in shared_form_classes),
                    f'{path}:{content.count(chr(10), 0, match.start()) + 1} {form_tag}',
                )

    def test_shouldGiveEveryRuntimeTableASharedDensityContract(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        shared_table_classes = (
            'responsive-admin-table',
            'dashboard-dense-table',
        )

        # Then
        for path in template_dir.rglob('*.html'):
            content = path.read_text(encoding='utf-8')
            for match in re.finditer(r'<table\b[^>]*>', content, flags=re.IGNORECASE):
                table_tag = match.group(0)
                self.assertTrue(
                    any(shared_class in table_tag for shared_class in shared_table_classes),
                    f'{path}:{content.count(chr(10), 0, match.start()) + 1} {table_tag}',
                )

    def test_shouldUseToolFormContractForLightweightDashboardForms(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        tool_form_templates = [
            template_dir / 'ai_dashboard_workflow.html',
            template_dir / 'task_forecast.html',
            template_dir / 'workbench.html',
            template_dir / 'partials' / 'bug_trend_content.html',
            template_dir / 'partials' / 'bug_trend_evidence.html',
            template_dir / 'partials' / 'current_tasks_filters.html',
            template_dir / 'partials' / 'pull_request_filters.html',
        ]

        # Then
        for path in tool_form_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-tool-form', content, str(path))
            self.assertIn('dashboard-tool-grid', content, str(path))
            self.assertIn('dashboard-tool-field', content, str(path))
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
        self.assertIn('.dashboard-action-form', css)
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
