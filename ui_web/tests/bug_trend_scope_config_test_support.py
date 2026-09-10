from pathlib import Path

from playwright.sync_api import sync_playwright

from bug_metrics.app.api import bug_trend_api
from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption


class FakeScopeMetadataFacade:
    def __init__(self):
        self.selected_projects = []

    def get_scope_config(self, scope_id):
        from bug_metrics.app.api import bug_trend_api
        return bug_trend_api.get_scope_config(scope_id)

    def scope_config_from_post(self, post_data):
        from ui_web.facades.bug_trend_facade import BugTrendFacade
        from bug_metrics.app.api import bug_trend_api
        return BugTrendFacade(bug_trend_api).scope_config_from_post(post_data)

    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {'warnings': ['Metadata refresh failed: offline'], 'options': None}


class FakeSuccessfulScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return ScopeConfigOptions(
            projects=[TrackerOption('STDEL', 'STDEL')],
            item_types=[TrackerOption('1', 'Bug')],
            statuses=[TrackerOption('11', 'Open')],
            resolutions=[TrackerOption('21', 'Fixed')],
            priorities=[TrackerOption('31', 'P1-Critical')],
            fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
            components=[TrackerOption('41', 'Emulation')],
            versions=[TrackerOption('51', '2026.01')],
        )


class FakePartialScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {
            'warnings': ['Unable to load component metadata'],
            'options': ScopeConfigOptions(
                projects=[TrackerOption('STDEL', 'STDEL')],
                fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
            ),
        }




class BugTrendScopeConfigViewTestSupport:
    def _post_payload(self, scope, critical_high_values):
        return {
            'id': str(scope.id),
            'name': scope.name,
            'ip': scope.ip,
            'project_label': scope.project_label,
            'jql': scope.jql,
            'bug_type_values': '\n'.join(scope.bug_type_values),
            'open_status_values': '\n'.join(scope.open_status_values),
            'fixed_status_values': '\n'.join(scope.fixed_status_values),
            'closed_status_values': '\n'.join(scope.closed_status_values),
            'terminal_excluded_status_values': '\n'.join(scope.terminal_excluded_status_values),
            'fixed_resolution_values': '\n'.join(scope.fixed_resolution_values),
            'closed_resolution_values': '\n'.join(scope.closed_resolution_values),
            'reopen_status_values': '\n'.join(scope.reopen_status_values),
            'severity_field': scope.severity_field,
            'critical_high_values': critical_high_values,
            'medium_low_values': '\n'.join(scope.medium_low_values),
            'component_field': scope.component_field,
            'owner_field': scope.owner_field,
            'team_field': scope.team_field,
            'milestone_field': scope.milestone_field,
            'fix_version_field': scope.fix_version_field,
            'package_version_field': scope.package_version_field,
            'display_fields': '\n'.join(scope.display_fields),
            'timezone': scope.timezone,
            'bucket_granularity': scope.bucket_granularity,
            'enabled': 'on',
        }

    def _measure_scope_config_provider_tabs(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'desktop': self._measure_scope_config_provider_tabs_viewport(browser, html, 1440, 900),
                'phone': self._measure_scope_config_provider_tabs_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_config_dirty_state(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                initial_dirty_fields = page.locator('.is-dirty-field').count()
                page.fill('#scope-name', 'Unsaved scope name')
                return page.evaluate("""
                    initialDirtyFields => {
                        const field = document.querySelector('#scope-name');
                        const shell = field.closest('.scope-config-form-field');
                        const label = document.querySelector('label[for="scope-name"]');
                        const banner = document.querySelector('[data-dirty-banner]');
                        const cancel = document.querySelector('.scope-editor-actions button[value="discard"]');
                        const actions = document.querySelector('.scope-editor-actions');
                        const heights = Array.from(actions.querySelectorAll('.button'))
                            .map(button => Math.round(button.getBoundingClientRect().height))
                            .filter(height => height > 0);
                        return {
                            initial_dirty_fields: initialDirtyFields,
                            dirty_field_highlighted: shell.classList.contains('is-dirty-field'),
                            dirty_control_highlighted: field.classList.contains('is-dirty-control'),
                            dirty_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                            dirty_label_text: label ? label.innerText : '',
                            cancel_button_visible: cancel ? cancel.getBoundingClientRect().height > 0 : false,
                            action_button_height_delta: Math.max(...heights) - Math.min(...heights),
                            action_gap_px: Math.round(parseFloat(getComputedStyle(actions).columnGap || getComputedStyle(actions).gap || '0')),
                            page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        };
                    }
                """, initial_dirty_fields)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_required_validation(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.click('.scope-editor-actions button[value="save_draft"]')
                save_draft = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                page.fill('#scope-name', 'Required visual scope')
                page.fill('#scope-jql', 'project = STDEL')
                page.fill('#scope-bug-types', 'Bug')
                page.click('.scope-editor-actions button[value="save_enable"]')
                enable = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                return {
                    'save_draft_missing_names': save_draft['missing_names'],
                    'save_draft_summary_visible': save_draft['summary_visible'],
                    'save_draft_focused_id': save_draft['focused_id'],
                    'save_draft_messages': save_draft['messages'],
                    'enable_missing_names': enable['missing_names'],
                    'enable_summary_visible': enable['summary_visible'],
                    'enable_focused_id': enable['focused_id'],
                    'enable_messages': enable['messages'],
                }
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_config_provider_tabs_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const shell = document.querySelector('.scope-config-provider-panel.provider-tab-shell');
                    const tabBody = document.querySelector('.provider-tab-body');
                    const contextGrid = document.querySelector('.scope-provider-grid');
                    const detailPanel = document.querySelector('.scope-provider-detail-panel');
                    const profileSelect = document.querySelector('select[name="profile_id"]');
                    const selectedTab = document.querySelector('.provider-tab-list [aria-selected="true"]');
                    const selectedCheck = selectedTab ? selectedTab.querySelector('.provider-tab-check') : null;
                    const providerChoiceHeights = Array.from(document.querySelectorAll('.provider-tab-list .provider-setup-choice'))
                        .map(choice => Math.round(choice.getBoundingClientRect().height));
                    const formControlHeights = Array.from(document.querySelectorAll('.scope-config-form-field .input, .scope-config-form-field select'))
                        .map(control => Math.round(control.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const maxHeight = values => values.length ? Math.max(...values) : 0;
                    const minHeight = values => values.length ? Math.min(...values) : 0;
                    const shellBorderColor = shell ? getComputedStyle(shell).borderLeftColor : '';
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        tab_count: document.querySelectorAll('.provider-tab-list [role="tab"]').length,
                        selected_check_visible: selectedCheck ? selectedCheck.getBoundingClientRect().width >= 14 : false,
                        tab_shell_wraps_provider_content: Boolean(
                            shell && contextGrid && detailPanel && profileSelect
                            && shell.contains(contextGrid)
                            && shell.contains(detailPanel)
                            && shell.contains(profileSelect)
                        ),
                        tab_body_visible: tabBody ? tabBody.getBoundingClientRect().height > 0 : false,
                        selected_tab_attached_to_body: Boolean(
                            selectedTab && tabBody
                            && Math.abs(selectedTab.getBoundingClientRect().bottom - tabBody.getBoundingClientRect().top) <= 2
                        ),
                        selected_tab_is_hsdes: selectedTab ? selectedTab.textContent.includes('HSD-ES') : false,
                        shell_border_is_blue: shellBorderColor === 'rgb(28, 126, 214)',
                        detail_panel_left_border_width: detailPanel ? Math.round(parseFloat(getComputedStyle(detailPanel).borderLeftWidth)) : 0,
                        provider_choice_max_height: maxHeight(providerChoiceHeights),
                        scope_form_control_height_delta: maxHeight(formControlHeights) - minHeight(formControlHeights),
                    };
                }
            """)
        finally:
            page.close()

    def _measure_scope_library_row_actions(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        html = html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            import_file_visible_initial = page.locator('.scope-import-panel').is_visible()
            page.locator('.scope-import-menu summary').click()
            import_file_visible_after_open = page.locator('.scope-import-panel').is_visible()
            page.locator('.scope-import-menu').evaluate('menu => { menu.open = false; }')
            page.locator('.scope-library-header .title').hover()
            page.wait_for_timeout(180)
            help_result = page.evaluate("""
                () => {
                    const helpTip = document.querySelector('.help-tip');
                    const iconHelpTip = document.querySelector('.help-tip.is-icon');
                    const helpTipBubble = helpTip ? getComputedStyle(helpTip, '::after') : null;
                    const helpTipRect = helpTip ? helpTip.getBoundingClientRect() : null;
                    const iconHelpTipRect = iconHelpTip ? iconHelpTip.getBoundingClientRect() : null;
                    return {
                        help_tip_visible_on_hover: helpTipBubble ? Number(helpTipBubble.opacity) > 0.9 : false,
                        help_tip_width: helpTipRect ? Math.round(helpTipRect.width) : 0,
                        icon_help_tip_width: iconHelpTipRect ? Math.round(iconHelpTipRect.width) : 0,
                    };
                }
            """)
            page.locator('.scope-row-menu summary').first.click()
            result = page.evaluate("""
                () => {
                    const actions = document.querySelector('tbody tr .scope-primary-actions');
                    const primaryButtons = Array.from(actions.querySelectorAll(':scope > .button, :scope > .scope-row-menu > summary.button'));
                    const primaryRects = primaryButtons.map(button => button.getBoundingClientRect());
                    const panel = actions.querySelector('.workbench-menu-panel').getBoundingClientRect();
                    const cell = actions.closest('td').getBoundingClientRect();
                    const menu = actions.querySelector('.scope-row-menu');
                    const archiveButton = actions.querySelector('button[value="disable"]');
                    const archiveRect = archiveButton ? archiveButton.getBoundingClientRect() : null;
                    return {
                        same_row: primaryRects.length >= 2 && Math.abs(primaryRects[0].top - primaryRects[1].top) <= 1,
                        primary_heights: Array.from(new Set(primaryRects.map(rect => Math.round(rect.height)))).sort((a, b) => a - b),
                        primary_widths: Array.from(new Set(primaryRects.map(rect => Math.round(rect.width)))).sort((a, b) => a - b),
                        panel_width: Math.round(panel.width),
                        action_cell_width: Math.round(cell.width),
                        archive_action_visible: archiveRect !== null && archiveRect.width > 0 && archiveRect.height > 0,
                        horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        open_after_summary_click: menu.open,
                    };
                }
            """)
            result.update(help_result)
            result['import_file_visible_initial'] = import_file_visible_initial
            result['import_file_visible_after_open'] = import_file_visible_after_open
            page.mouse.click(20, 20)
            result['open_after_blank_click'] = page.locator('.scope-row-menu').first.evaluate('menu => menu.open')
            page.locator('.scope-row-menu summary').first.click()
            page.keyboard.press('Escape')
            result['open_after_escape'] = page.locator('.scope-row-menu').first.evaluate('menu => menu.open')
            return result
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _measure_scope_library_delete_confirmation(self, html, confirmation):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            page.locator('button[value="delete_archived"]').evaluate("button => { button.closest('details').open = true; }")
            page.evaluate("""
                confirmation => {
                    window.__deleteResult = {
                        submitted: false,
                        confirm_message: '',
                        prompt_message: '',
                        prompt_default: '',
                        posted_confirmation: '',
                    };
                    window.confirm = message => {
                        window.__deleteResult.confirm_message = message;
                        return true;
                    };
                    window.prompt = (message, defaultValue) => {
                        window.__deleteResult.prompt_message = message;
                        window.__deleteResult.prompt_default = defaultValue || '';
                        return confirmation;
                    };
                    const form = document.querySelector('button[value="delete_archived"]').closest('form');
                    form.addEventListener('submit', event => {
                        event.preventDefault();
                        window.__deleteResult.submitted = true;
                        window.__deleteResult.posted_confirmation = new FormData(form).get('delete_confirmation') || '';
                    });
                }
            """, confirmation)
            page.locator('button[value="delete_archived"]').click()
            return page.evaluate("() => window.__deleteResult")
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _measure_scope_library_responsive_table(self, html):
        html = self._scope_library_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'wide': self._measure_scope_library_viewport(browser, html, 1920, 900),
                'desktop': self._measure_scope_library_viewport(browser, html, 1532, 768),
                'medium': self._measure_scope_library_viewport(browser, html, 1180, 820),
                'phone': self._measure_scope_library_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_scope_library_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('.scope-library-table tbody tr'));
                    const bodyRowHeights = rows.map(row => Math.round(row.getBoundingClientRect().height));
                    const primaryActionLeftOffsets = rows
                        .map(row => {
                            const cell = row.querySelector('td.scope-col-actions');
                            const actions = row.querySelector('.scope-primary-actions');
                            if (!cell || !actions) {
                                return null;
                            }
                            return Math.round(actions.getBoundingClientRect().left - cell.getBoundingClientRect().left);
                        })
                        .filter(offset => offset !== null);
                    const firstActions = document.querySelector('tbody tr .scope-primary-actions');
                    const actionRects = firstActions
                        ? Array.from(firstActions.querySelectorAll(':scope > .button, :scope > form .button, :scope > .scope-row-menu > summary.button')).map(button => button.getBoundingClientRect())
                        : [];
                    const hashCell = document.querySelector('.scope-library-table tbody td.scope-col-hash');
                    const ipCell = document.querySelector('.scope-library-table tbody td.scope-col-ip');
                    const projectCell = document.querySelector('.scope-library-table tbody td.scope-col-project');
                    const lifecycle = document.querySelector('.scope-lifecycle-guide');
                    const thead = document.querySelector('.scope-library-table thead');
                    const firstCell = document.querySelector('.scope-library-table tbody td');
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        table_horizontal_overflow: document.querySelector('.scope-library-table-box').scrollWidth > document.querySelector('.scope-library-table-box').clientWidth + 1,
                        scope_lifecycle_height: lifecycle ? Math.round(lifecycle.getBoundingClientRect().height) : 0,
                        max_body_row_height: Math.max(...bodyRowHeights),
                        actions_wrap: actionRects.length >= 2 && Math.abs(actionRects[0].top - actionRects[1].top) > 1,
                        primary_action_left_offset_delta: Math.max(...primaryActionLeftOffsets) - Math.min(...primaryActionLeftOffsets),
                        hash_column_display: hashCell ? getComputedStyle(hashCell).display : '',
                        ip_column_display: ipCell ? getComputedStyle(ipCell).display : '',
                        project_column_display: projectCell ? getComputedStyle(projectCell).display : '',
                        thead_display: thead ? getComputedStyle(thead).display : '',
                        first_cell_display: firstCell ? getComputedStyle(firstCell).display : '',
                    };
                }
            """)
        finally:
            page.close()

    def _scope_library_browser_html(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        return html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )
