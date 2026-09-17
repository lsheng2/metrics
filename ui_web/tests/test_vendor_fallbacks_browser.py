from pathlib import Path

from django.test import TestCase
from playwright.sync_api import sync_playwright


class TestVendorFallbacksBrowser(TestCase):
    def test_shouldIncludeClosestFormFieldsForButtonHxGet(self):
        # Given
        script = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'vendor_fallbacks.js').read_text(encoding='utf-8')
        html = f"""
            <html>
              <head><base href="http://fallback.test/"></head>
              <body>
                <form>
                  <input type="hidden" name="source_mode" value="query_builder">
                  <input type="hidden" name="query_builder_project" value="STDEL">
                  <input name="selected_projects" value="">
                  <button type="button" hx-get="/metadata/" hx-include="closest form" hx-target="#target">Refresh metadata</button>
                </form>
                <div id="target"></div>
                <script>{script}</script>
              </body>
            </html>
        """

        # When
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            requested_urls = []
            page.route('**/metadata/**', lambda route: (
                requested_urls.append(route.request.url),
                route.fulfill(status=200, content_type='text/html', body='<p>ok</p>'),
            ))
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.locator('button', has_text='Refresh metadata').click()
                page.wait_for_timeout(200)
            finally:
                browser.close()

        # Then
        self.assertEqual(1, len(requested_urls))
        self.assertIn('source_mode=query_builder', requested_urls[0])
        self.assertIn('query_builder_project=STDEL', requested_urls[0])

    def test_shouldApplyOutOfBandSwapFromButtonHxGetResponse(self):
        # Given
        script = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'vendor_fallbacks.js').read_text(encoding='utf-8')
        html = f"""
            <html>
              <head><base href="http://fallback.test/"></head>
              <body>
                <form>
                  <button type="button" hx-get="/metadata/" hx-target="#scope-metadata-options">Refresh metadata</button>
                </form>
                <div id="query-builder-controls"><p>Old query controls</p></div>
                <div id="scope-metadata-options"></div>
                <script>{script}</script>
              </body>
            </html>
        """
        response = """
            <div id="query-builder-controls" hx-swap-oob="innerHTML">
              <input name="query_builder_issue_types" value="Bug">
            </div>
            <section class="metadata-result">Metadata refreshed</section>
        """

        # When
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route('**/metadata/**', lambda route: route.fulfill(status=200, content_type='text/html', body=response))
            try:
                page.set_content(html, wait_until='domcontentloaded')
                page.locator('button', has_text='Refresh metadata').click()
                page.wait_for_timeout(200)
                result = page.evaluate("""() => ({
                    queryControlInputs: document.querySelectorAll('#query-builder-controls input[name="query_builder_issue_types"]').length,
                    oldQueryControlsPresent: document.querySelector('#query-builder-controls').innerText.includes('Old query controls'),
                    metadataResultPresent: Boolean(document.querySelector('#scope-metadata-options .metadata-result')),
                    nestedQueryControls: document.querySelectorAll('#scope-metadata-options #query-builder-controls').length,
                })""")
            finally:
                browser.close()

        # Then
        self.assertEqual(1, result['queryControlInputs'])
        self.assertFalse(result['oldQueryControlsPresent'])
        self.assertTrue(result['metadataResultPresent'])
        self.assertEqual(0, result['nestedQueryControls'])
