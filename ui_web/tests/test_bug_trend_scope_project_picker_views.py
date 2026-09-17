from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.app.api import bug_trend_api
from ui_web.facades.bug_trend_facade import BugTrendFacade
from ui_web.tests.bug_trend_scope_config_test_support import FakeSuccessfulScopeMetadataApi


class TestBugTrendScopeProjectPickerViews(TestCase):
    def test_shouldChooseJiraProjectFromSearchableMetadataPickerInBrowser(self):
        # Given
        with patch('ui_web.views.bug_trend_scope_views.ui_web_container') as container:
            container.bug_trend_facade = BugTrendFacade(bug_trend_api, FakeSuccessfulScopeMetadataApi())
            response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                'mode': 'new',
                'refresh_metadata': '1',
                'source_mode': 'query_builder',
            })

        # When
        result = self._measure_project_picker(response.content.decode())

        # Then
        self.assertEqual(['STDEL'], result['visible_labels'])
        self.assertEqual('STDEL', result['selected_value'])
        self.assertEqual(['STDEL'], result['selected_options'])
        self.assertEqual('project = STDEL', result['preview_value'])
        self.assertTrue(result['menu_hidden_after_select'])
        self.assertTrue(result['dirty_field_highlighted'])
        self.assertTrue(result['manual_project_input_visible'])

    def _measure_project_picker(self, html):
        html = self._browser_html(html)
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            picker = page.locator('[data-query-builder-project-picker] [data-searchable-value-picker]')
            picker.locator('[data-searchable-value-picker-toggle]').click()
            picker.locator('[data-searchable-value-picker-search]').fill('std')
            visible_labels = picker.locator('[data-searchable-value-picker-option]:visible').evaluate_all(
                'options => options.map(option => option.textContent.trim())'
            )
            picker.locator('[data-searchable-value-picker-option][data-searchable-value-picker-value="STDEL"]').click()
            return page.evaluate("""
                labels => {
                    const field = document.querySelector('input[name="query_builder_project"]');
                    const menu = document.querySelector('[data-query-builder-project-picker] [data-searchable-value-picker-menu]');
                    const shell = field.closest('.scope-config-form-field');
                    return {
                        visible_labels: labels,
                        selected_value: field.value,
                        selected_options: Array.from(document.querySelectorAll('[data-query-builder-project-picker] [data-searchable-value-picker-option][aria-selected="true"]')).map(option => option.textContent.trim()),
                        preview_value: document.querySelector('#query-builder-preview').value,
                        menu_hidden_after_select: menu.hidden,
                        dirty_field_highlighted: shell.classList.contains('is-dirty-field'),
                        manual_project_input_visible: Boolean(document.querySelector('input#query-builder-project')?.offsetParent),
                    };
                }
            """, visible_labels)
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _browser_html(self, html):
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
