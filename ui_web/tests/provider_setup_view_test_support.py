import json
from pathlib import Path

from playwright.sync_api import sync_playwright


class ProviderSetupViewTestSupport:
    def _profile_payload(self):
        return {
            'action': 'save_draft',
            'id': '',
            'profile_id': 'new-provider-profile',
            'provider_id': 'jira',
            'display_name': 'New Provider Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'source_population': json.dumps({'native_query_text': 'project = NEW'}),
            'scope_labels': json.dumps({'ip': 'new-ip', 'project_or_product': 'new-project'}),
            'field_bindings': json.dumps({'severity': {'native_field': 'priority'}}),
            'value_mappings': json.dumps({'bug_type_values': ['Bug']}),
            'chart_bindings': json.dumps({'open_bug_trend': {'support_status': 'supported'}}),
            'sync_policy': json.dumps({'live_sync': 'supported'}),
            'readiness_policy': json.dumps({'ready_status': 'ready'}),
        }

    def _hsdes_profile_payload(self):
        payload = self._profile_payload()
        payload.update({
            'profile_id': 'new-hsdes-profile',
            'provider_id': 'hsdes',
            'display_name': 'New HSD-ES Profile',
            'connection_base_url': 'https://hsdes-api.intel.com/rest',
            'connection_auth_mode': 'kerberos',
            'credential_ref': 'profile:local',
            'source_population': json.dumps({'provider_id': 'hsdes', 'ownership_type': 'provider_owned_saved_query'}),
            'field_bindings': json.dumps({'item_id': {'native_field': 'id'}}),
            'chart_bindings': json.dumps({'component_bug': {'support_status': 'supported_from_seed_facts'}}),
        })
        return payload

    def _measure_provider_setup_layout(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'desktop': self._measure_provider_setup_viewport(browser, html, 1440, 900),
                'phone': self._measure_provider_setup_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_setup_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const editor = document.querySelector('.provider-setup-editor');
                    const advanced = document.querySelector('.provider-advanced-config');
                    const tableBox = document.querySelector('.provider-profile-table-box');
                    const shell = document.querySelector('.provider-tab-shell');
                    const tabBody = document.querySelector('.provider-tab-body');
                    const contextPanel = document.querySelector('.provider-context-panel');
                    const identityRow = document.querySelector('.provider-identity-row');
                    const actions = document.querySelector('.provider-editor-actions');
                    const selectedCheck = document.querySelector('.provider-setup-choice.is-selected .provider-tab-check');
                    const selectedTab = document.querySelector('.provider-tab-list [aria-selected="true"]');
                    const primaryButtons = Array.from(document.querySelectorAll('.provider-row-primary-actions > .button, .provider-row-primary-actions > .provider-row-menu > summary.button'));
                    const primaryButtonHeights = primaryButtons
                        .map(button => Math.round(button.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const providerChoiceHeights = Array.from(document.querySelectorAll('.provider-setup-choice'))
                        .map(choice => Math.round(choice.getBoundingClientRect().height));
                    const formControlHeights = Array.from(document.querySelectorAll('.provider-form-field .input, .provider-form-field select'))
                        .map(control => Math.round(control.getBoundingClientRect().height))
                        .filter(height => height > 0);
                    const maxHeight = values => values.length ? Math.max(...values) : 0;
                    const minHeight = values => values.length ? Math.min(...values) : 0;
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        table_horizontal_overflow: tableBox ? tableBox.scrollWidth > tableBox.clientWidth + 1 : false,
                        inventory_visible: tableBox ? tableBox.getBoundingClientRect().height > 0 : false,
                        editor_visible: editor ? editor.getBoundingClientRect().height > 0 : false,
                        provider_choice_count: document.querySelectorAll('.scope-provider-choice').length,
                        advanced_json_open: advanced ? advanced.open : false,
                        primary_action_button_height_delta: maxHeight(primaryButtonHeights) - minHeight(primaryButtonHeights),
                        provider_choice_max_height: maxHeight(providerChoiceHeights),
                        selected_check_visible: selectedCheck ? selectedCheck.getBoundingClientRect().width >= 14 : false,
                        tab_shell_wraps_context: Boolean(shell && contextPanel && identityRow && shell.contains(contextPanel) && shell.contains(identityRow)),
                        tab_body_visible: tabBody ? tabBody.getBoundingClientRect().height > 0 : false,
                        selected_tab_attached_to_body: Boolean(
                            selectedTab && tabBody
                            && Math.abs(selectedTab.getBoundingClientRect().bottom - tabBody.getBoundingClientRect().top) <= 2
                        ),
                        tab_shell_wraps_editor_controls: Boolean(shell && advanced && actions && shell.contains(advanced) && shell.contains(actions)),
                        context_panel_left_border_width: contextPanel ? Math.round(parseFloat(getComputedStyle(contextPanel).borderLeftWidth)) : 0,
                        provider_form_control_height_delta: maxHeight(formControlHeights) - minHeight(formControlHeights),
                    };
                }
            """)
        finally:
            page.close()

    def _provider_setup_browser_html(self, html):
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

    def _measure_provider_auth_visibility(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                return page.evaluate("""
                    () => {
                        const activePanel = document.querySelector('.provider-auth-panel:not(.is-hidden)');
                        const inactiveInputs = Array.from(document.querySelectorAll('.provider-auth-panel.is-hidden input'));
                        const inactiveInputsDisabledBeforeSwitch = inactiveInputs.every(input => input.disabled);
                        const select = document.querySelector('[data-provider-auth-select]');
                        let cloudEmailVisibleAfterSwitch = false;
                        let cloudEmailValueAfterSwitch = '';
                        if (select) {
                            select.value = 'cloud_basic';
                            select.dispatchEvent(new Event('change', { bubbles: true }));
                            const cloudEmail = document.querySelector('#provider-connection-email');
                            cloudEmailVisibleAfterSwitch = Boolean(
                                cloudEmail
                                && !cloudEmail.disabled
                                && !cloudEmail.closest('.provider-auth-panel').classList.contains('is-hidden')
                            );
                            cloudEmailValueAfterSwitch = cloudEmail ? cloudEmail.value : '';
                        }
                        return {
                            initial_active_text: activePanel ? activePanel.innerText : '',
                            inactive_inputs_disabled: inactiveInputsDisabledBeforeSwitch,
                            cloud_email_visible_after_switch: cloudEmailVisibleAfterSwitch,
                            cloud_email_value_after_switch: cloudEmailValueAfterSwitch,
                        };
                    }
                """)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_connection_test_result_layout(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                return page.evaluate("""
                    () => {
                        const result = document.querySelector('#provider-connection-test-result');
                        const actions = document.querySelector('.provider-editor-actions');
                        return {
                            result_visible: result ? result.getBoundingClientRect().height > 0 : false,
                            result_before_actions: Boolean(
                                result && actions
                                && result.getBoundingClientRect().bottom <= actions.getBoundingClientRect().top + 1
                            ),
                            result_text: result ? result.innerText : '',
                        };
                    }
                """)
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_dirty_state(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                initial_dirty_fields = page.locator('.is-dirty-field').count()
                page.fill('#provider-hsdes-saved-query-id', '15017652869')
                dirty_state = page.evaluate("""
                    () => {
                        const field = document.querySelector('#provider-hsdes-saved-query-id');
                        const shell = field.closest('.provider-form-field');
                        const label = document.querySelector('label[for="provider-hsdes-saved-query-id"]');
                        const banner = document.querySelector('[data-dirty-banner]');
                        const cancel = document.querySelector('[data-dirty-reset]');
                        const actions = document.querySelector('.provider-editor-actions');
                        const heights = Array.from(actions.querySelectorAll('.button'))
                            .map(button => Math.round(button.getBoundingClientRect().height))
                            .filter(height => height > 0);
                        return {
                            dirty_field_highlighted: shell.classList.contains('is-dirty-field'),
                            dirty_control_highlighted: field.classList.contains('is-dirty-control'),
                            dirty_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                            dirty_label_text: label ? label.innerText : '',
                            cancel_button_visible: cancel ? cancel.getBoundingClientRect().height > 0 : false,
                            action_button_height_delta: Math.max(...heights) - Math.min(...heights),
                            action_gap_px: Math.round(parseFloat(getComputedStyle(actions).columnGap || getComputedStyle(actions).gap || '0')),
                        };
                    }
                """)
                page.click('[data-dirty-reset]')
                after_cancel = page.evaluate("""
                    () => {
                        const banner = document.querySelector('[data-dirty-banner]');
                        return {
                            after_cancel_value: document.querySelector('#provider-hsdes-saved-query-id').value,
                            after_cancel_dirty_fields: document.querySelectorAll('.is-dirty-field').length,
                            after_cancel_banner_visible: banner ? !banner.classList.contains('is-hidden') : false,
                        };
                    }
                """)
                return {'initial_dirty_fields': initial_dirty_fields, **dirty_state, **after_cancel}
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()

    def _measure_provider_required_validation(self, html):
        html = self._provider_setup_browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 820})
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.click('.provider-editor-actions button[value="save_draft"]')
                save_draft = page.evaluate("""
                    () => ({
                        missing_names: Array.from(document.querySelectorAll('.is-required-missing-control')).map(field => field.name),
                        summary_visible: !document.querySelector('[data-required-summary]').classList.contains('is-hidden'),
                        focused_id: document.activeElement.id,
                        messages: Array.from(document.querySelectorAll('.dashboard-required-message')).map(message => message.textContent),
                    })
                """)
                page.fill('#provider-profile-id', 'hsdes-required-test')
                page.fill('#provider-display-name', 'HSD-ES Required Test')
                page.click('.provider-editor-actions button[value="test_connection"]')
                test_connection = page.evaluate("""
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
                    'test_connection_missing_names': test_connection['missing_names'],
                    'test_connection_summary_visible': test_connection['summary_visible'],
                    'test_connection_focused_id': test_connection['focused_id'],
                    'test_connection_messages': test_connection['messages'],
                }
            finally:
                page.close()
        finally:
            browser.close()
            playwright.stop()
