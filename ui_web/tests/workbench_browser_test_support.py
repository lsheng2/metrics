from pathlib import Path

from playwright.sync_api import sync_playwright


class WorkbenchBrowserTestSupport:
    def _render_workbench_chart_and_click_evidence(self, response, evidence_response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.route('**/workbench/**', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body='<div id="workbench-grid"><div id="bug-trend-evidence-container">'
                     + evidence_response.content.decode()
                     + '</div></div>',
            ))
            page.route('**/partials/bug-trend/evidence/**', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=evidence_response.content.decode(),
            ))
            page.set_content(self._browser_html(response.content.decode()), wait_until='domcontentloaded')
            page.wait_for_function("window.bugTrendChartInstance !== undefined")
            nonblank_pixels = page.locator('#bugTrendChart').evaluate("""
                canvas => {
                    const context = canvas.getContext('2d');
                    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
                    for (let index = 3; index < pixels.length; index += 4) {
                        if (pixels[index] !== 0) return true;
                    }
                    return false;
                }
            """)
            page.locator('#bugTrendChart').click(position={'x': 410, 'y': 170})
            page.locator('#bug-trend-evidence-container').wait_for()
            chart_config = page.evaluate("""
                () => {
                    const config = window.bugTrendChartInstance.config;
                    config.evidenceUrl = window.lastHtmxUrl;
                    return config;
                }
            """)
            return nonblank_pixels, page.locator('#bug-trend-evidence-container').inner_text(), chart_config
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _post_grafana_selection_message(self, html):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            page.evaluate("""
                () => window.postMessage({
                    type: 'metrics-workbench:grafana-selection',
                    scope_id: '1',
                    begin: '2026-08-03',
                    end: '2026-08-09',
                    chart_id: 'default_bug_trend',
                    chart_version: '1',
                    run: 'run-1',
                    bucket: 'bucket-1',
                    series: 'new_critical_high'
                }, window.location.origin)
            """)
            page.wait_for_function("window.lastHtmxCall !== undefined")
            return (
                page.evaluate("window.lastHtmxCall.url"),
                page.evaluate("window.location.pathname + window.location.search"),
                page.evaluate("window.lastHtmxCall.target"),
            )
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _browser_html(self, html):
        html = html.replace(
            '<script src="/static/js/vendor_fallbacks.js"></script>',
            '<script>' + self._htmx_stub() + self._chart_stub() + '</script>',
        )
        external_assets = [
            '<script src="/static/js/main.js"></script>',
            '<link rel="stylesheet" href="/static/css/vendor_fallbacks.css">',
            '<link rel="stylesheet" href="/static/css/main.css">',
        ]
        for asset in external_assets:
            html = html.replace(asset, '')
        return html

    def _chart_stub(self):
        return """
            window.Chart = function(context, config) {
                this.config = config;
                context.fillStyle = '#eb5757';
                context.fillRect(20, 20, 160, 80);
                context.canvas.addEventListener('click', function(event) {
                    if (config.options && config.options.onClick) {
                        config.options.onClick(event, [{ index: 0, datasetIndex: 2 }]);
                    }
                });
                this.destroy = function() {};
            };
        """

    def _htmx_stub(self):
        return """
            window.htmx = {
                ajax: function(method, url, options) {
                    window.lastHtmxUrl = url;
                    if (url.startsWith('/')) {
                        url = 'http://testserver' + url;
                    }
                    return fetch(url).then(function(response) { return response.text(); }).then(function(html) {
                        document.querySelector(options.target).innerHTML = html;
                    });
                }
            };
        """
