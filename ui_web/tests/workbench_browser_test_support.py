from playwright.sync_api import sync_playwright

from ui_web.tests import ui_geometry_contract as geometry
from ui_web.tests.dashboard_asset_support import (
    feature_scripts_source,
    inline_dashboard_assets,
    strip_static_asset_tags,
)

SPLITTER_ARIA_SCRIPT = (
    "element => ({now: element.getAttribute('aria-valuenow'), "
    "min: element.getAttribute('aria-valuemin'), max: element.getAttribute('aria-valuemax')})"
)
GRAFANA_PANEL_THEME_SCRIPT = "panel => new URL(panel.src).searchParams.get('theme')"
PHONE_STACK_SCRIPT = """() => {
    const rect = selector => document.querySelector(selector).getBoundingClientRect();
    const root = document.documentElement;
    const grid = rect('#workbench-grid');
    const shell = rect('.workbench-shell');
    const panes = Array.from(document.querySelectorAll('[data-workbench-pane]'), pane => [pane.dataset.workbenchPane, pane.getBoundingClientRect()]);
    return {
        scroll_locked: [root, document.body].some(element => getComputedStyle(element).overflowY === 'hidden'),
        topbar_display: getComputedStyle(document.querySelector('.app-topbar')).display,
        pane_order: panes.sort((a, b) => a[1].top - b[1].top).map(([name]) => name),
        pane_width_delta: Math.max(...panes.map(([, pane]) => Math.abs(pane.width - grid.width))),
        gutter_delta: Math.abs(shell.left - (root.clientWidth - shell.right)),
        chart_frame_height: rect('[data-workbench-pane="chart"] .bug-trend-chart-frame').height,
        pane_header_overlap: Math.max(...Array.from(document.querySelectorAll('.workbench-pane-header'), header => {
            const [lead, ...rest] = header.children;
            const leadRight = Math.max(...[lead, ...lead.querySelectorAll('*')].map(node => node.getBoundingClientRect().right));
            return rest.length ? leadRight - rest.at(-1).getBoundingClientRect().left : -Infinity;
        })),
        pane_title_lines: Array.from(document.querySelectorAll('.workbench-pane-title'), title => {
            const range = document.createRange();
            range.selectNodeContents(title.firstChild);
            return new Set(Array.from(range.getClientRects(), line => Math.round(line.top))).size;
        }),
    };
}"""
PHONE_DETAIL_SCRIPT = """() => {
    const rect = selector => document.querySelector(selector).getBoundingClientRect();
    const detail = rect('[data-workbench-ticket-detail]');
    return {
        splitter_displays: Array.from(document.querySelectorAll('[data-workbench-splitter]'), splitter => getComputedStyle(splitter).display),
        evidence_columns: getComputedStyle(document.querySelector('[data-workbench-evidence-layout]')).gridTemplateColumns.split(' ').length,
        detail_gap_below_table: detail.top - rect('[data-workbench-evidence-layout] .workbench-evidence-table-wrap').bottom,
        detail_under_topbar: rect('.app-topbar').bottom - detail.top,
        detail_under_status_bar: detail.bottom - rect('[data-workbench-status-bar]').top,
    };
}"""
PHONE_AI_SCRIPT = """() => {
    const ai = document.querySelector('[data-workbench-pane="ai-assistant"]');
    return {
        ai_under_status_bar: ai.getBoundingClientRect().bottom - document.querySelector('[data-workbench-status-bar]').getBoundingClientRect().top,
        ai_width_delta: Math.abs(ai.getBoundingClientRect().width - document.querySelector('#workbench-grid').getBoundingClientRect().width),
        ai_body_display: getComputedStyle(ai.querySelector('.workbench-pane-body')).display,
    };
}"""


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
        html = inline_dashboard_assets(self._browser_html(response.content.decode()))
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
            detail_created = page.locator('[data-ticket-detail-created]').inner_text()
            page.locator('[data-workbench-splitter="ticket-detail"]').press('ArrowLeft')
            ticket_splitter_aria = page.locator('[data-workbench-splitter="ticket-detail"]').evaluate(SPLITTER_ARIA_SCRIPT)
            ticket_detail_width = page.locator('[data-workbench-evidence-layout]').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--workbench-ticket-detail-width').trim()"
            )
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
            page.locator('#workbench-chart-title').click(position={'x': 4, 'y': 4})
            columns_menu_open_after_blank_click = page.locator('[data-workbench-evidence-workspace] .workbench-menu').first.evaluate(
                "menu => menu.open"
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
            chart_splitter_aria = page.locator('[data-workbench-splitter="chart-evidence"]').evaluate(SPLITTER_ARIA_SCRIPT)
            page.locator('[data-workbench-ticket-detail-close]').click()
            detail_collapsed_after_close = page.locator('[data-workbench-evidence-layout]').evaluate(
                "element => element.classList.contains('is-detail-collapsed')"
            )
            page.locator('[data-workbench-collapse="ai-assistant"]').click()
            ai_collapsed = page.locator('#workbench-grid').evaluate(
                "element => element.classList.contains('is-ai-collapsed')"
            )
            ai_button_text = page.locator('[data-workbench-collapse="ai-assistant"]').inner_text()
            ai_title_visible = page.locator('#workbench-ai-title').is_visible()
            page.locator('[data-workbench-splitter="main-ai"]').press('ArrowLeft')
            ai_width = page.locator('#workbench-grid').evaluate(
                "element => getComputedStyle(element).getPropertyValue('--workbench-ai-width').trim()"
            )
            ai_splitter_aria = page.locator('[data-workbench-splitter="main-ai"]').evaluate(SPLITTER_ARIA_SCRIPT)
            page.locator('[data-workbench-collapse="ai-assistant"]').click()
            layout_metrics = page.evaluate("""
                limits => {
                    const app = document.querySelector('[data-dashboard-layout]').getBoundingClientRect();
                    const sidebar = document.querySelector('[data-dashboard-sidebar]').getBoundingClientRect();
                    const shell = document.querySelector('.workbench-shell').getBoundingClientRect();
                    const ai = document.querySelector('[data-workbench-pane="ai-assistant"]').getBoundingClientRect();
                    const status = document.querySelector('[data-workbench-status-bar]').getBoundingClientRect();
                    const toolbar = document.querySelector('.workbench-toolbar').getBoundingClientRect();
                    const labels = Array.from(document.querySelectorAll('.workbench-toolbar-field .label')).map(label => {
                        const field = label.closest('.workbench-toolbar-field').getBoundingClientRect();
                        const rect = label.getBoundingClientRect();
                        return {
                            text: label.innerText.trim(),
                            clipped: label.scrollHeight > Math.ceil(label.clientHeight) + limits.OVERFLOW_TOLERANCE || label.scrollWidth > Math.ceil(label.clientWidth) + limits.OVERFLOW_TOLERANCE,
                            outsideField: rect.top < field.top - limits.ALIGNMENT_TOLERANCE || rect.bottom > field.bottom + limits.ALIGNMENT_TOLERANCE,
                            topGap: Math.round(rect.top - toolbar.top),
                        };
                    });
                    return {
                        appTop: Math.round(app.top),
                        sidebarTop: Math.round(sidebar.top),
                        shellTop: Math.round(shell.top),
                        shellRightGap: Math.round(window.innerWidth - shell.right),
                        aiRightGap: Math.round(window.innerWidth - ai.right),
                        aiWidth: Math.round(ai.width),
                        aiWidthVar: getComputedStyle(document.querySelector('#workbench-grid')).getPropertyValue('--workbench-ai-width').trim(),
                        statusBottomGap: Math.round(window.innerHeight - status.bottom),
                        statusHeight: Math.round(status.height),
                        toolbarLabelClippingCount: labels.filter(label => label.clipped || label.outsideField).length,
                        toolbarMinLabelTopGap: Math.min(...labels.map(label => label.topGap)),
                    };
                }
            """, geometry.browser_limits())
            page.reload(wait_until='domcontentloaded')
            restored_ai_collapsed = page.locator('#workbench-grid').evaluate(
                "element => element.classList.contains('is-ai-collapsed')"
            )
            restored_ai_button_text = page.locator('[data-workbench-collapse="ai-assistant"]').inner_text()
            restored_ai_title_visible = page.locator('#workbench-ai-title').is_visible()
            return {
                'initial_detail_collapsed': initial_detail_collapsed,
                'detail_open': detail_open,
                'detail_issue': detail_issue,
                'detail_created': detail_created,
                'ticket_splitter_aria': ticket_splitter_aria,
                'ticket_detail_width': ticket_detail_width,
                'selected_count': selected_count,
                'selected_ticket_payload': selected_ticket_payload,
                'bulk_detail_issue': bulk_detail_issue,
                'status_column_hidden': status_column_hidden,
                'columns_menu_open_after_blank_click': columns_menu_open_after_blank_click,
                'first_issue_after_sort': first_issue_after_sort,
                'chart_collapsed': chart_collapsed,
                'chart_height': chart_height,
                'chart_splitter_aria': chart_splitter_aria,
                'detail_collapsed_after_close': detail_collapsed_after_close,
                'ai_collapsed': ai_collapsed,
                'ai_button_text': ai_button_text,
                'ai_title_visible': ai_title_visible,
                'ai_width': ai_width,
                'ai_splitter_aria': ai_splitter_aria,
                'layout_metrics': layout_metrics,
                'restored_ai_collapsed': restored_ai_collapsed,
                'restored_ai_button_text': restored_ai_button_text,
                'restored_ai_title_visible': restored_ai_title_visible,
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_phone_layout(self, response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        html = inline_dashboard_assets(self._browser_html(response.content.decode()))
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            # A wheel event counts as the user scrolling, which turns off the Workbench initial scroll-to-top guard.
            page.evaluate("window.dispatchEvent(new WheelEvent('wheel'))")
            result = page.evaluate(PHONE_STACK_SCRIPT)
            last_row = page.locator('[data-workbench-ticket-row]').last
            last_row.evaluate("row => row.scrollIntoView({block: 'end'})")
            last_row.click()
            result.update(page.evaluate(PHONE_DETAIL_SCRIPT))
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            result['ai_under_status_bar'] = page.evaluate(PHONE_AI_SCRIPT)['ai_under_status_bar']
            page.locator('[data-workbench-collapse="ai-assistant"]').click()
            collapsed = page.evaluate(PHONE_AI_SCRIPT)
            result['collapsed_ai_width_delta'] = collapsed['ai_width_delta']
            result['collapsed_ai_body_display'] = collapsed['ai_body_display']
            result['collapsed_ai_title_visible'] = page.locator('#workbench-ai-title').is_visible()
            result['collapsed_ai_button_text'] = page.locator('[data-workbench-collapse="ai-assistant"]').inner_text()
            return result
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_navigation_state_restore(self):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        main_js = feature_scripts_source()
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
                    '/workbench/?scope_id=7'
                );
            """)
            page.reload(wait_until='domcontentloaded')
            restored_href = page.locator('#workbench-link').get_attribute('href')

            page.evaluate("window.localStorage.setItem('metricsWorkbench.lastUrl', 'https://example.com/workbench/?scope_id=1')")
            page.reload(wait_until='domcontentloaded')
            rejected_href = page.locator('#workbench-link').get_attribute('href')

            page.goto('http://testserver/workbench/?scope_id=11', wait_until='domcontentloaded')
            saved_url = page.evaluate("window.localStorage.getItem('metricsWorkbench.lastUrl')")
            saved_href = page.locator('#workbench-link').get_attribute('href')
            return restored_href, rejected_href, saved_url, saved_href
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _post_ai_base_open_grafana_host_action(self, response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        main_js = feature_scripts_source()
        html = self._browser_html(response.content.decode()).replace('</body>', f'<script>{main_js}</script></body>')
        child_html = """
            <html>
            <body>
                <script>
                    window.hostActionAck = null;
                    window.addEventListener('message', event => {
                        if (event.data && event.data.type === 'ai-base.host-action.result') {
                            window.hostActionAck = event.data.result;
                        }
                    });
                </script>
            </body>
            </html>
        """
        try:
            page.route('http://testserver/workbench/**', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.route('http://127.0.0.1:48310/child.html', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=child_html,
            ))
            page.goto('http://testserver/workbench/?scope_id=7', wait_until='domcontentloaded')
            page.evaluate("""
                () => {
                    window.htmx = {
                        ajax(method, url, options) {
                            window.lastHtmxCall = { method, url, target: options.target, select: options.select };
                        }
                    };
                    const frame = document.createElement('iframe');
                    frame.src = 'http://127.0.0.1:48310/child.html';
                    document.body.appendChild(frame);
                }
            """)
            page.locator('iframe[src="http://127.0.0.1:48310/child.html"]').wait_for()
            frame = page.locator('iframe[src="http://127.0.0.1:48310/child.html"]').element_handle().content_frame()
            frame.wait_for_load_state('domcontentloaded')
            frame.evaluate("""
                () => window.parent.postMessage({
                    type: 'ai-base.host-action.request',
                    request: {
                        sourceAppId: 'metrics-dashboard',
                        bindingKey: 'metrics.grafana.publish',
                        sessionId: 'session-1',
                        requestId: 'hostact-1',
                        artifactId: 'artifact-1',
                        correlationId: 'corr-1',
                        idempotencyKey: 'artifact-1:open-chart',
                        actionKind: 'metrics.openGrafanaChart',
                        payload: {
                            profileId: 'chiplet-2a-jira',
                            providerId: 'jira',
                            chartId: 'open_bug_trend',
                            panelId: 1,
                            dashboardUid: 'metrics-bug-trend-c-stock'
                        }
                    }
                }, 'http://testserver')
            """)
            page.wait_for_function("() => window.lastHtmxCall !== undefined")
            frame.wait_for_function("() => window.hostActionAck !== null")
            return {
                'htmx_call': page.evaluate("() => window.lastHtmxCall"),
                'ack': frame.evaluate("() => window.hostActionAck"),
                'location': page.evaluate("() => window.location.href"),
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_scope_sync_and_sidebar_resize(self, response, target_scope_id, target_response=None):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        main_js = feature_scripts_source()
        html = self._browser_html(response.content.decode()).replace('</body>', f'<script>{main_js}</script></body>')
        target_html = html
        if target_response is not None:
            target_html = self._browser_html(target_response.content.decode()).replace('</body>', f'<script>{main_js}</script></body>')
        try:
            def fulfill_workbench(route):
                body = target_html if '?' in route.request.url else html
                route.fulfill(status=200, content_type='text/html', body=body)

            page.route('**/workbench/**', fulfill_workbench)
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
            page.wait_for_function("window.lastHtmxUrl !== undefined")
            htmx_url = page.evaluate("window.lastHtmxUrl")
            page.wait_for_timeout(100)
            profile_value = page.locator('#workbench-profile').input_value()
            provider_value = page.locator('#workbench-provider').input_value()
            return {
                'initial_sidebar_width': initial_sidebar_width,
                'resized_sidebar_width': resized_sidebar_width,
                'stored_sidebar_width': stored_sidebar_width,
                'htmx_url': htmx_url,
                'profile_value': profile_value,
                'provider_value': provider_value,
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _exercise_workbench_standalone_ai_disabled(self, response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        main_js = feature_scripts_source()
        html = self._browser_html(response.content.decode()).replace('</body>', f'<script>{main_js}</script></body>')
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            chart_visible = page.locator('[data-workbench-pane="chart"]').is_visible()
            evidence_visible = page.locator('[data-workbench-ticket-row]').first.is_visible()
            ai_diagnostic_visible = page.get_by_text('AI chat is not enabled for this Dashboard process.').is_visible()
            iframe_count = page.locator('.workbench-ai-chat-frame').count()
            page.locator('[data-workbench-collapse="ai-assistant"]').click()
            ai_collapsed = page.locator('#workbench-grid').evaluate(
                "element => element.classList.contains('is-ai-collapsed')"
            )
            return {
                'chart_visible': chart_visible,
                'evidence_visible': evidence_visible,
                'ai_diagnostic_visible': ai_diagnostic_visible,
                'iframe_count': iframe_count,
                'ai_collapsed': ai_collapsed,
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _browser_html(self, html):
        return strip_static_asset_tags(html).replace(
            '</head>',
            '<script>' + self._htmx_stub() + self._chart_stub() + '</script></head>',
            1,
        )

    def _exercise_grafana_preview_theme(self, response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900}, color_scheme='light')
        html = inline_dashboard_assets(
            self._browser_html(response.content.decode()),
            scripts=('js/shell.js', 'js/grafana-embeds.js'),
        )
        try:
            page.route('http://testserver/workbench/', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body=html,
            ))
            page.route('http://grafana.test/**', lambda route: route.fulfill(
                status=200,
                content_type='text/html',
                body='<!doctype html><title>Panel</title>',
            ))
            page.goto('http://testserver/workbench/', wait_until='domcontentloaded')
            panel = page.locator('.workbench-grafana-panel')
            src_before_open = panel.get_attribute('src')
            page.locator('.workbench-grafana-preview > summary').click()
            page.wait_for_function("() => document.querySelector('.workbench-grafana-panel').hasAttribute('src')", timeout=5000)
            src_after_open = panel.get_attribute('src')
            theme_after_open = panel.evaluate(GRAFANA_PANEL_THEME_SCRIPT)
            page.locator('[data-theme-choice="dark"]').click()
            theme_after_switch = panel.evaluate(GRAFANA_PANEL_THEME_SCRIPT)
            return {
                'src_before_open': src_before_open,
                'src_after_open': src_after_open,
                'theme_after_open': theme_after_open,
                'theme_after_switch': theme_after_switch,
            }
        finally:
            page.close()
            browser.close()
            playwright.stop()

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
