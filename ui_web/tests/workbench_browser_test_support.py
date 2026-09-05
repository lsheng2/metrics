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

    def _exercise_workbench_high_density_interactions(self, response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        main_js = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
        test_css = '<style>[data-dashboard-layout]{--dashboard-sidebar-width:248px;display:flex}[data-dashboard-sidebar]{width:var(--dashboard-sidebar-width);flex:0 0 var(--dashboard-sidebar-width)}</style>'
        html = self._browser_html(response.content.decode()).replace('</body>', f'{test_css}<script>{main_js}</script></body>')
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            initial_detail_collapsed = page.locator('[data-workbench-evidence-layout]').evaluate(
                "element => element.classList.contains('is-detail-collapsed')"
            )
            page.locator('[data-workbench-ticket-row]').first.click()
            detail_open = page.locator('[data-ticket-detail-content]').is_visible()
            detail_issue = page.locator('[data-ticket-detail-issue]').inner_text()
            page.locator('[data-workbench-ticket-select-all]').check()
            selected_count = page.locator('[data-workbench-ticket-selected-count]').inner_text()
            selected_ticket_payload = page.evaluate("window.metricsWorkbenchSelectedTickets")
            page.locator('[data-workbench-ticket-bulk]').click()
            bulk_detail_issue = page.locator('[data-ticket-detail-issue]').inner_text()
            page.locator('summary:has-text("Columns")').click()
            page.locator('[data-workbench-column-toggle="status"]').uncheck()
            status_column_hidden = page.locator('[data-workbench-field="status"]').first.evaluate(
                "element => element.classList.contains('is-hidden')"
            )
            page.locator('[data-workbench-evidence-sort-field]').select_option('owner')
            page.locator('[data-workbench-evidence-sort-direction]').select_option('asc')
            page.locator('[data-workbench-evidence-sort]').click()
            first_issue_after_sort = page.locator('[data-workbench-ticket-row]').first.get_attribute('data-issue-key')
            page.locator('[data-workbench-collapse="chart"]').click()
            chart_collapsed = page.locator('#workbench-grid').evaluate(
                "element => element.classList.contains('is-chart-collapsed')"
            )
            page.locator('[data-workbench-splitter="chart-evidence"]').press('ArrowDown')
            chart_height = page.locator('#workbench-grid').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--workbench-chart-height').trim()"
            )
            page.locator('[data-workbench-ticket-detail-close]').click()
            detail_collapsed_after_close = page.locator('[data-workbench-evidence-layout]').evaluate(
                "element => element.classList.contains('is-detail-collapsed')"
            )
            page.locator('[data-workbench-collapse="ai-assistant"]').click()
            ai_collapsed = page.locator('#workbench-grid').evaluate(
                "element => element.classList.contains('is-ai-collapsed')"
            )
            page.locator('[data-workbench-splitter="main-ai"]').press('ArrowLeft')
            ai_width = page.locator('#workbench-grid').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--workbench-ai-width').trim()"
            )
            return {
                'initial_detail_collapsed': initial_detail_collapsed,
                'detail_open': detail_open,
                'detail_issue': detail_issue,
                'selected_count': selected_count,
                'selected_ticket_payload': selected_ticket_payload,
                'bulk_detail_issue': bulk_detail_issue,
                'status_column_hidden': status_column_hidden,
                'first_issue_after_sort': first_issue_after_sort,
                'chart_collapsed': chart_collapsed,
                'chart_height': chart_height,
                'detail_collapsed_after_close': detail_collapsed_after_close,
                'ai_collapsed': ai_collapsed,
                'ai_width': ai_width,
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_navigation_state_restore(self):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        main_js = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
        html = f"""
            <html>
            <body>
                <ul class="menu-list">
                    <li><a id="workbench-link" href="/workbench/" data-workbench-nav-link>Workbench</a></li>
                </ul>
                <section class="workbench-shell">
                    <div id="workbench-grid"></div>
                </section>
                <script>{main_js}</script>
            </body>
            </html>
        """
        try:
            page.route('**/*', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/current-tasks/', wait_until='domcontentloaded')
            page.evaluate("""
                window.localStorage.setItem(
                    'metricsWorkbench.lastUrl',
                    '/workbench/?scope_id=7&profile_id=chiplet-2a-jira&provider_id=jira'
                );
            """)
            page.reload(wait_until='domcontentloaded')
            restored_href = page.locator('#workbench-link').get_attribute('href')

            page.evaluate("window.localStorage.setItem('metricsWorkbench.lastUrl', 'https://example.com/workbench/?scope_id=1')")
            page.reload(wait_until='domcontentloaded')
            rejected_href = page.locator('#workbench-link').get_attribute('href')

            page.goto('http://testserver/workbench/?scope_id=11&profile_id=nvu-ttl-hsdes&provider_id=hsdes', wait_until='domcontentloaded')
            saved_url = page.evaluate("window.localStorage.getItem('metricsWorkbench.lastUrl')")
            saved_href = page.locator('#workbench-link').get_attribute('href')
            return restored_href, rejected_href, saved_url, saved_href
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_scope_sync_and_sidebar_resize(self, response, target_scope_id):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        main_js = (Path(__file__).resolve().parents[1] / 'static' / 'js' / 'main.js').read_text(encoding='utf-8')
        html = self._browser_html(response.content.decode()).replace('</body>', f'<script>{main_js}</script></body>')
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            page.locator('[data-dashboard-layout]').evaluate(
                "element => element.style.setProperty('--dashboard-sidebar-width', '248px')"
            )
            page.locator('[data-dashboard-sidebar]').evaluate(
                "element => { element.style.width = 'var(--dashboard-sidebar-width)'; element.style.flex = '0 0 var(--dashboard-sidebar-width)'; }"
            )
            initial_sidebar_width = page.locator('[data-dashboard-layout]').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--dashboard-sidebar-width').trim()"
            )
            page.locator('[data-dashboard-sidebar-splitter]').evaluate(
                "element => element.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))"
            )
            resized_sidebar_width = page.locator('[data-dashboard-layout]').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--dashboard-sidebar-width').trim()"
            )
            stored_sidebar_width = page.evaluate("window.localStorage.getItem('metricsDashboard.sidebarWidth')")
            page.locator('#workbench-scope').select_option(str(target_scope_id))
            profile_value = page.locator('#workbench-profile').input_value()
            provider_value = page.locator('#workbench-provider').input_value()
            return {
                'initial_sidebar_width': initial_sidebar_width,
                'resized_sidebar_width': resized_sidebar_width,
                'stored_sidebar_width': stored_sidebar_width,
                'profile_value': profile_value,
                'provider_value': provider_value,
            }
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
