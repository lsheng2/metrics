import json
from datetime import date, datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendBucketIssue,
    BugTrendCalculationRun,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
    ProviderProfileConfig,
)


class UiDesignBrowserMetricsSupport:
    def _measure_baseline_pages(self, pages):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            results = {}
            for label, html, expectations in pages:
                browser_html = self._browser_html(html)
                results[label] = {
                    'desktop': self._measure_viewport(browser, browser_html, expectations, 1440, 900),
                    'phone': self._measure_viewport(browser, browser_html, expectations, 390, 900),
                }
            return results
        finally:
            browser.close()
            playwright.stop()

    def _measure_visual_manifest_pages(self, pages, viewports):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            results = {}
            for label, html in pages:
                browser_html = self._browser_html(html)
                results[label] = {}
                for viewport in viewports:
                    results[label][viewport['name']] = self._measure_visual_manifest_viewport(
                        browser,
                        browser_html,
                        viewport['width'],
                        viewport['height'],
                    )
            return results
        finally:
            browser.close()
            playwright.stop()

    def _measure_required_submit(self, html, submitter_selector):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.set_content(self._browser_html(html), wait_until='domcontentloaded')
            page.click(submitter_selector)
            return page.evaluate("""
                () => {
                    const invalidFields = Array.from(document.querySelectorAll('.is-required-missing-control'));
                    const summary = document.querySelector('[data-required-summary]');
                    return {
                        invalid_field_names: invalidFields.map(field => field.name),
                        invalid_aria_count: invalidFields.filter(field => field.getAttribute('aria-invalid') === 'true').length,
                        missing_shell_count: document.querySelectorAll('.is-missing-required').length,
                        summary_visible: Boolean(summary && !summary.classList.contains('is-hidden') && summary.textContent.trim()),
                    };
                }
            """)
        finally:
            browser.close()
            playwright.stop()

    def _measure_visual_manifest_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const visible = element => Boolean(
                        element
                        && (element.offsetWidth || element.offsetHeight || element.getClientRects().length)
                    );
                    const buttonName = button => (
                        button.getAttribute('aria-label')
                        || button.getAttribute('title')
                        || button.innerText
                        || ''
                    ).trim();
                    const buttons = Array.from(document.querySelectorAll('button, a.button')).filter(visible);
                    const clippedButtons = buttons
                        .filter(button => button.innerText.trim())
                        .filter(button => button.scrollWidth > Math.ceil(button.clientWidth) + 1)
                        .map(button => button.innerText.trim());
                    const unnamedIconButtons = buttons
                        .filter(button => button.querySelector('i[class*="iconoir"], svg'))
                        .filter(button => !buttonName(button))
                        .map(button => button.outerHTML.slice(0, 120));
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        clipped_buttons: clippedButtons,
                        unnamed_icon_buttons: unnamedIconButtons,
                    };
                }
            """)
        finally:
            page.close()

    def _measure_viewport(self, browser, html, expectations, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                expectations => {
                    const visible = element => Boolean(
                        element
                        && (element.offsetWidth || element.offsetHeight || element.getClientRects().length)
                    );
                    const max = values => values.length ? Math.max(...values) : 0;
                    const min = values => values.length ? Math.min(...values) : 0;
                    const heightDelta = selector => {
                        const heights = Array.from(document.querySelectorAll(selector))
                            .filter(visible)
                            .map(element => Math.round(element.getBoundingClientRect().height))
                            .filter(value => value > 0);
                        return max(heights) - min(heights);
                    };
                    const heightDeltaWithin = (root, selector) => {
                        const heights = Array.from(root.querySelectorAll(selector))
                            .filter(visible)
                            .map(element => Math.round(element.getBoundingClientRect().height))
                            .filter(value => value > 0);
                        return max(heights) - min(heights);
                    };
                    const tableName = (table, index) => {
                        const id = table.id ? `#${table.id}` : '';
                        const className = table.className ? `.${String(table.className).trim().replace(/\\s+/g, '.')}` : '';
                        return `table[${index}]${id}${className}`;
                    };
                    const actionButtons = Array.from(document.querySelectorAll('.dashboard-action-bar .button')).filter(visible);
                    const clippedActionButtons = actionButtons
                        .filter(button => button.scrollWidth > Math.ceil(button.clientWidth) + 1)
                        .map(button => button.innerText.trim());
                    const buttonMetricFailures = [];
                    Array.from(document.querySelectorAll('.dashboard-action-bar, .dashboard-action-group, .dashboard-tool-actions, .scope-primary-actions, .provider-row-primary-actions, .workbench-evidence-actions'))
                        .filter(visible)
                        .forEach((group, index) => {
                            const buttons = Array.from(group.querySelectorAll('button, a.button')).filter(visible);
                            const heights = buttons.map(button => button.getBoundingClientRect().height).filter(value => value > 0);
                            const delta = max(heights) - min(heights);
                            const clipped = buttons
                                .filter(button => button.innerText.trim())
                                .filter(button => button.scrollWidth > Math.ceil(button.clientWidth) + 1)
                                .map(button => button.innerText.trim());
                            if (delta > 1) {
                                buttonMetricFailures.push(`group ${index} height delta ${delta.toFixed(1)}px`);
                            }
                            if (clipped.length) {
                                buttonMetricFailures.push(`group ${index} clipped ${clipped.join(', ')}`);
                            }
                        });
                    const formMetricFailures = [];
                    Array.from(document.querySelectorAll('.dashboard-tool-form, .dashboard-edit-form'))
                        .filter(visible)
                        .forEach((form, index) => {
                            const controlDelta = heightDeltaWithin(form, '.dashboard-tool-field .input, .dashboard-tool-field select, .dashboard-form-field .input, .dashboard-form-field select');
                            const buttonDelta = heightDeltaWithin(form, '.dashboard-tool-actions .button, .dashboard-action-bar .button, .dashboard-action-group .button');
                            if (controlDelta > 1) {
                                formMetricFailures.push(`form ${index} control height delta ${controlDelta}px`);
                            }
                            if (buttonDelta > 1) {
                                formMetricFailures.push(`form ${index} button height delta ${buttonDelta}px`);
                            }
                        });
                    const selectedChecks = Array.from(document.querySelectorAll('.provider-setup-choice.is-selected .provider-tab-check'))
                        .filter(visible);
                    const tables = Array.from(document.querySelectorAll('table')).filter(visible);
                    const denseTables = tables.filter(table => table.classList.contains('dashboard-dense-table'));
                    const tableContractFailures = [];
                    const tableDensityFailures = [];
                    const tableButtonFailures = [];
                    const denseTableRowHeights = [];
                    const denseTableButtonHeightDeltas = [];
                    tables.forEach((table, index) => {
                        const name = tableName(table, index);
                        const hasContract = table.classList.contains('responsive-admin-table')
                            || table.classList.contains('dashboard-dense-table');
                        if (!hasContract) {
                            tableContractFailures.push(name);
                            return;
                        }
                        const cells = Array.from(table.querySelectorAll('th, td')).filter(visible);
                        const maxPaddingBlock = max(cells.map(cell => {
                            const style = getComputedStyle(cell);
                            return parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
                        }));
                        if (maxPaddingBlock > 12) {
                            tableDensityFailures.push(`${name} padding ${maxPaddingBlock.toFixed(1)}px`);
                        }
                        const bodyRows = Array.from(table.querySelectorAll('tbody tr')).filter(visible);
                        const maxDenseRowHeight = max(bodyRows.map(row => row.getBoundingClientRect().height));
                        if (table.classList.contains('dashboard-dense-table') && maxDenseRowHeight > 72) {
                            tableDensityFailures.push(`${name} row ${maxDenseRowHeight.toFixed(1)}px`);
                        }
                        const tableButtons = Array.from(table.querySelectorAll('button, a.button')).filter(visible);
                        const tableButtonHeights = tableButtons.map(button => button.getBoundingClientRect().height).filter(value => value > 0);
                        const tableButtonHeightDelta = max(tableButtonHeights) - min(tableButtonHeights);
                        if (table.classList.contains('dashboard-dense-table')) {
                            denseTableRowHeights.push(...bodyRows.map(row => row.getBoundingClientRect().height).filter(value => value > 0));
                            denseTableButtonHeightDeltas.push(tableButtonHeightDelta);
                        }
                        const clippedTableButtons = tableButtons
                            .filter(button => button.innerText.trim())
                            .filter(button => button.scrollWidth > Math.ceil(button.clientWidth) + 1)
                            .map(button => button.innerText.trim());
                        if (tableButtonHeightDelta > 1) {
                            tableButtonFailures.push(`${name} height delta ${tableButtonHeightDelta.toFixed(1)}px`);
                        }
                        if (clippedTableButtons.length) {
                            tableButtonFailures.push(`${name} clipped ${clippedTableButtons.join(', ')}`);
                        }
                    });
                    return {
                        expects_editor: Boolean(expectations.editor),
                        expects_provider_tabs: Boolean(expectations.provider_tabs),
                        expects_table: Boolean(expectations.table),
                        expects_dense_table: Boolean(expectations.dense_table),
                        expects_tool_form: Boolean(expectations.tool_form),
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        visible_button_count: Array.from(document.querySelectorAll('.button')).filter(visible).length,
                        clipped_action_buttons: clippedActionButtons,
                        responsive_table_count: document.querySelectorAll('.responsive-admin-table').length,
                        dense_table_count: denseTables.length,
                        dense_table_max_row_height: max(denseTableRowHeights),
                        dense_table_button_height_delta: max(denseTableButtonHeightDeltas),
                        table_contract_failures: tableContractFailures,
                        table_density_failures: tableDensityFailures,
                        table_button_failures: tableButtonFailures,
                        button_metric_failures: buttonMetricFailures,
                        form_metric_failures: formMetricFailures,
                        tool_form_count: document.querySelectorAll('.dashboard-tool-form').length,
                        tool_grid_count: document.querySelectorAll('.dashboard-tool-grid').length,
                        tool_form_dirty_count: document.querySelectorAll('.dashboard-tool-form[data-dirty-form], .dashboard-tool-form[data-required-form]').length,
                        tool_form_button_height_delta: heightDelta('.dashboard-tool-form .button'),
                        tool_form_control_height_delta: heightDelta('.dashboard-tool-field .input, .dashboard-tool-field select'),
                        provider_tab_shell_count: document.querySelectorAll('.provider-tab-shell').length,
                        selected_provider_check_visible: selectedChecks.some(check => check.getBoundingClientRect().width >= 14),
                        required_summary_count: document.querySelectorAll('[data-required-summary]').length,
                        dirty_banner_count: document.querySelectorAll('[data-dirty-banner]').length,
                        action_bar_count: document.querySelectorAll('.dashboard-action-bar').length,
                        action_bar_button_height_delta: heightDelta('.dashboard-action-bar .button'),
                        editor_control_height_delta: heightDelta('.dashboard-form-field .input, .dashboard-form-field select'),
                    };
                }
            """, expectations)
        finally:
            page.close()

    def _browser_html(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        if '</head>' not in html:
            html = self._fragment_html(html)
        return html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )

    def _jira_profile_payload(self, profile_id):
        return {
            'action': 'enable_profile',
            'id': '',
            'profile_id': profile_id,
            'provider_id': 'jira',
            'display_name': 'Monkey Jira Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'connection_base_url': 'https://jira.example.test',
            'connection_auth_mode': 'server_pat',
            'credential_ref': 'profile:local',
            'source_population': json.dumps({'native_query_text': 'project = MONKEY'}),
            'scope_labels': json.dumps({'ip': 'monkey-ip', 'project_or_product': 'monkey-project'}),
            'field_bindings': json.dumps({'severity': {'native_field': 'priority'}}),
            'value_mappings': json.dumps({'bug_type_values': ['Bug']}),
            'chart_bindings': json.dumps({'open_bug_trend': {'support_status': 'supported'}}),
            'sync_policy': json.dumps({'live_sync': 'supported'}),
            'readiness_policy': json.dumps({'ready_status': 'ready'}),
        }

    def _hsdes_profile_payload(self, profile_id):
        return {
            'action': 'enable_profile',
            'id': '',
            'profile_id': profile_id,
            'provider_id': 'hsdes',
            'display_name': 'Monkey HSD-ES Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'connection_base_url': 'https://hsdes-api.example.test/rest',
            'connection_auth_mode': 'kerberos',
            'credential_ref': 'profile:local',
            'hsdes_saved_query_id': '15017652869',
            'hsdes_tenant': 'ip_fw_sw_sensing.tenant',
            'hsdes_subject': 'ip_fw_sw_sensing.bug',
            'source_population': json.dumps({
                'provider_id': 'hsdes',
                'ownership_type': 'provider_owned_saved_query',
            }),
            'scope_labels': json.dumps({'ip': 'NVU', 'project_or_product': 'NVU1.0_TTL'}),
            'field_bindings': json.dumps({'item_id': {'native_field': 'id'}}),
            'value_mappings': json.dumps({'bug_type_values': ['bug']}),
            'chart_bindings': json.dumps({'component_bug': {'support_status': 'supported_from_seed_facts'}}),
            'sync_policy': json.dumps({'live_sync': 'configuration_required'}),
            'readiness_policy': json.dumps({'ready_status': 'seeded_preview'}),
        }

    def _scope_payload(self, name, profile_id):
        return {
            'action': 'save_enable',
            'id': '',
            'name': name,
            'ip': 'MONKEY',
            'project_label': 'Monkey',
            'jql': 'project = MONKEY',
            'bug_type_values': 'Bug',
            'open_status_values': 'Open',
            'fixed_status_values': 'Fixed',
            'closed_status_values': 'Closed',
            'terminal_excluded_status_values': '',
            'fixed_resolution_values': '',
            'closed_resolution_values': '',
            'reopen_status_values': '',
            'severity_field': 'priority',
            'critical_high_values': 'P1-Critical',
            'medium_low_values': 'P3-Medium',
            'component_field': 'components',
            'owner_field': 'assignee',
            'team_field': '',
            'milestone_field': '',
            'fix_version_field': '',
            'package_version_field': '',
            'display_fields': '',
            'timezone': 'UTC',
            'bucket_granularity': 'weekly',
            'provider_id': 'jira',
            'profile_id': profile_id,
        }

    def _seed_bound_scope_with_run(self):
        scope = JiraScopeConfig.objects.create(
            name='Baseline Workbench Scope',
            jql='project = BASELINE',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        run, bucket = self._seed_run_and_issue(scope)
        return scope, run, bucket

    def _seed_run_and_issue(self, scope):
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 9, 1),
            source_coverage_end=date(2026, 9, 7),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 9, 1),
            bucket_end=date(2026, 9, 7),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            new_critical_high_count=1,
            open_count=1,
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='MONKEY-1',
            summary='Monkey user visible ticket',
            status='Open',
            severity_value='P1-Critical',
            component_value='ui',
            owner_value='Monkey User',
            created_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )
        return run, bucket
