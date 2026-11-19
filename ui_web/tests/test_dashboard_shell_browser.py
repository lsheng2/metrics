"""Browser contract for the app shell: theme preference, command palette, sidebar rail and drawer."""
import tempfile
from urllib.parse import urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from ui_web.tests.dashboard_asset_support import inline_dashboard_assets

SHELL_ORIGIN = 'http://testserver'
RECORD_THEME_EVENTS = (
    "window.__themeEvents = [];"
    "document.addEventListener('dashboard:themechange', event => window.__themeEvents.push(event.detail.theme));"
)
THEME_STATE = """
() => ({
    theme: document.documentElement.dataset.theme,
    preference: document.documentElement.dataset.themePreference,
    stored: window.localStorage.getItem('dashboard-theme'),
    checked: document.querySelector('[data-theme-choice][aria-checked="true"]').dataset.themeChoice,
    focused: document.activeElement.dataset.themeChoice || null,
    systemHint: document.querySelector('[data-theme-choice="system"]').title,
    events: window.__themeEvents,
})
"""
SYSTEM_DARK_HINT = 'Match system theme (system appearance is dark)'
SYSTEM_LIGHT_HINT = 'Match system theme (system appearance is light)'


class TestDashboardShellBrowser(TestCase):
    def test_shouldFollowSystemAppearanceLiveUntilUserPinsATheme(self):
        # Given
        html = self._homepage_html()

        # When
        states = self._exercise_theme_preference(html)

        # Then
        self.assertEqual({
            'theme': 'dark', 'preference': 'system', 'stored': None, 'checked': 'system',
            'focused': None, 'systemHint': SYSTEM_DARK_HINT, 'events': [],
        }, states['system_dark'])
        self.assertEqual(('light', SYSTEM_LIGHT_HINT, ['light']), (
            states['system_turned_light']['theme'],
            states['system_turned_light']['systemHint'],
            states['system_turned_light']['events'],
        ))
        self.assertEqual(('dark', 'dark', 'dark', ['light', 'dark']), (
            states['pinned_dark']['theme'],
            states['pinned_dark']['stored'],
            states['pinned_dark']['checked'],
            states['pinned_dark']['events'],
        ))
        self.assertEqual(('dark', 'dark', SYSTEM_LIGHT_HINT, []), (
            states['pinned_after_reload']['theme'],
            states['pinned_after_reload']['checked'],
            states['pinned_after_reload']['systemHint'],
            states['pinned_after_reload']['events'],
        ))
        self.assertEqual(('light', 'system', 'system', 'system', ['light']), (
            states['keyboard_system']['theme'],
            states['keyboard_system']['stored'],
            states['keyboard_system']['checked'],
            states['keyboard_system']['focused'],
            states['keyboard_system']['events'],
        ))

    def test_shouldJumpWithCommandPaletteAndRememberCollapsedRail(self):
        # Given
        html = self._homepage_html()

        # When
        result = self._exercise_palette_and_rail(html)

        # Then
        self.assertTrue(result['palette_open'])
        self.assertTrue(result['input_focused'])
        self.assertEqual(['palette-data_health'], result['visible_options'])
        self.assertEqual('palette-data_health', result['active_descendant'])
        self.assertEqual(reverse('ui_web:data_health'), result['navigated_path'])
        self.assertEqual(('collapsed', 'true', 'false'), result['collapsed'])
        self.assertEqual('collapsed', result['collapsed_after_reload'])

    def test_shouldTrapPhoneNavigationInDrawerAndRestoreFocusOnEscape(self):
        # Given
        html = self._homepage_html()

        # When
        result = self._exercise_phone_drawer(html)

        # Then
        self.assertEqual({
            'drawer': 'open', 'main_inert': True, 'scrim_hidden': False,
            'opener_expanded': 'true', 'focus_in_sidebar': True,
        }, result['opened'])
        self.assertEqual({
            'drawer': None, 'main_inert': False, 'scrim_hidden': True,
            'opener_expanded': 'false', 'focus_on_opener': True,
        }, result['closed'])

    def test_shouldHideDrawerAtOnceWhenViewportCrossesPhoneBreakpoint(self):
        # Given
        html = self._homepage_html()

        # When
        crossing = self._cross_phone_breakpoint(html)

        # Then
        self.assertEqual({'visibility': 'hidden', 'covers_content': False}, crossing)

    def _homepage_html(self):
        with tempfile.TemporaryDirectory() as state_dir:
            with override_settings(METRICS_STATE_DIR=state_dir):
                response = self.client.get(reverse('ui_web:homepage'))
        self.assertEqual(200, response.status_code)
        return inline_dashboard_assets(response.content.decode(), scripts=('js/shell.js', 'js/command-palette.js'))

    def _open_shell(self, html, viewport, color_scheme='light'):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=viewport, color_scheme=color_scheme)
        context.add_init_script(RECORD_THEME_EVENTS)
        context.route(f'{SHELL_ORIGIN}/**', lambda route: route.fulfill(
            status=200,
            content_type='text/html',
            body=html if urlsplit(route.request.url).path == '/' else '<!doctype html><title>stub</title>',
        ))
        page = context.new_page()
        page.goto(f'{SHELL_ORIGIN}/', wait_until='domcontentloaded')
        return playwright, browser, page

    def _exercise_theme_preference(self, html):
        playwright, browser, page = self._open_shell(html, {'width': 1280, 'height': 800}, color_scheme='dark')
        try:
            states = {'system_dark': page.evaluate(THEME_STATE)}
            page.emulate_media(color_scheme='light')
            page.wait_for_function("document.documentElement.dataset.theme === 'light'")
            states['system_turned_light'] = page.evaluate(THEME_STATE)
            page.locator('[data-theme-choice="dark"]').click()
            states['pinned_dark'] = page.evaluate(THEME_STATE)
            page.reload(wait_until='domcontentloaded')
            states['pinned_after_reload'] = page.evaluate(THEME_STATE)
            page.locator('[data-theme-choice="dark"]').focus()
            page.keyboard.press('ArrowRight')
            states['keyboard_system'] = page.evaluate(THEME_STATE)
            return states
        finally:
            browser.close()
            playwright.stop()

    def _exercise_palette_and_rail(self, html):
        playwright, browser, page = self._open_shell(html, {'width': 1280, 'height': 800})
        try:
            page.keyboard.press('Control+K')
            palette = page.locator('[data-shell-palette]')
            palette.locator('[data-shell-palette-input]').fill('data health')
            result = {
                'palette_open': palette.evaluate('dialog => dialog.open'),
                'input_focused': page.evaluate("document.activeElement.matches('[data-shell-palette-input]')"),
                'visible_options': palette.locator('[role="option"]:not([hidden])').evaluate_all(
                    'options => options.map(option => option.id)'
                ),
                'active_descendant': palette.locator('[data-shell-palette-input]').get_attribute('aria-activedescendant'),
            }
            page.keyboard.press('Enter')
            page.wait_for_url(f'{SHELL_ORIGIN}{reverse("ui_web:data_health")}')
            result['navigated_path'] = urlsplit(page.url).path
            page.goto(f'{SHELL_ORIGIN}/', wait_until='domcontentloaded')
            page.keyboard.press('Control+Backslash')
            result['collapsed'] = (
                page.evaluate('document.documentElement.dataset.sidebar'),
                page.evaluate("window.localStorage.getItem('metricsDashboard.sidebarCollapsed')"),
                page.locator('[data-shell-collapse]').get_attribute('aria-expanded'),
            )
            page.reload(wait_until='domcontentloaded')
            result['collapsed_after_reload'] = page.evaluate('document.documentElement.dataset.sidebar')
            return result
        finally:
            browser.close()
            playwright.stop()

    def _exercise_phone_drawer(self, html):
        playwright, browser, page = self._open_shell(html, {'width': 390, 'height': 844})
        drawer_state = """
            () => ({
                drawer: document.documentElement.dataset.drawer || null,
                main_inert: document.querySelector('.app-main').inert,
                scrim_hidden: document.querySelector('[data-shell-scrim]').hidden,
                opener_expanded: document.querySelector('[data-shell-drawer-open]').getAttribute('aria-expanded'),
                focus_in_sidebar: document.getElementById('app-sidebar').contains(document.activeElement),
                focus_on_opener: document.activeElement.matches('[data-shell-drawer-open]'),
            })
        """
        try:
            page.locator('[data-shell-drawer-open]').click()
            opened = page.evaluate(drawer_state)
            page.keyboard.press('Escape')
            page.wait_for_function('!document.documentElement.dataset.drawer')
            closed = page.evaluate(drawer_state)
            opened.pop('focus_on_opener')
            closed.pop('focus_in_sidebar')
            return {'opened': opened, 'closed': closed}
        finally:
            browser.close()
            playwright.stop()

    def _cross_phone_breakpoint(self, html):
        playwright, browser, page = self._open_shell(html, {'width': 1280, 'height': 800})
        try:
            page.set_viewport_size({'width': 390, 'height': 844})
            return page.evaluate("""() => {
                const sidebar = document.getElementById('app-sidebar');
                return {visibility: getComputedStyle(sidebar).visibility,
                        covers_content: sidebar.contains(document.elementFromPoint(150, 400))};
            }""")
        finally:
            browser.close()
            playwright.stop()
