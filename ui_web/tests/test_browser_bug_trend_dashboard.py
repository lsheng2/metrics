from datetime import date, datetime, timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue

class TestBugTrendDashboardBrowser(TestCase):
    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldSyncMockJiraDataAndRenderDashboardEvidence(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When
        call_command(
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start', '2026-08-03',
            '--coverage-end', '2026-08-09',
            stdout=StringIO(),
        )
        run = BugTrendCalculationRun.objects.get(scope=scope, status=BugTrendCalculationRun.STATUS_COMPLETED)
        bucket = BugTrendBucket.objects.get(scope=scope, calculation_run=run)
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-09',
        })
        evidence_response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
        })
        nonblank_pixels, evidence_text, chart_config = self._render_chart_and_click_evidence(response, evidence_response)

        # Then
        self.assertTrue(nonblank_pixels)
        self.assertIn('fixed_or_closed_bugs tickets for 26WW32', evidence_text)
        self.assertIn('STDEL-8942', evidence_text)
        self.assertIn('run=' + str(run.id), chart_config['evidenceUrl'])
        self.assertIn('series=fixed_or_closed_bugs', chart_config['evidenceUrl'])
        self.assertEqual(1, bucket.fixed_or_closed_count)

    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldRenderTwoBucketDashboardFromRicherMockJiraData(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL richer trend',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        adapter_class.return_value.fetch_issues.return_value = [
            self._jira_issue_payload(
                issue_key='STDEL-9001',
                summary='Open critical backlog',
                status='Open',
                resolution=None,
                priority='P2-High',
                created='2026-08-04T10:00:00.000+0000',
                updated='2026-08-04T10:00:00.000+0000',
                histories=[],
            ),
            self._jira_issue_payload(
                issue_key='STDEL-9002',
                summary='Fixed medium bug in first week',
                status='Fixed',
                resolution='Fixed',
                priority='P3-Medium',
                created='2026-08-05T10:00:00.000+0000',
                updated='2026-08-06T10:00:00.000+0000',
                resolutiondate='2026-08-06T09:00:00.000+0000',
                histories=[self._status_history('2026-08-06T09:00:00.000+0000', 'Open', 'Fixed')],
            ),
            self._jira_issue_payload(
                issue_key='STDEL-9003',
                summary='Fixed critical bug in second week',
                status='Fixed',
                resolution='Fixed',
                priority='P1-Critical',
                created='2026-08-10T10:00:00.000+0000',
                updated='2026-08-14T10:00:00.000+0000',
                resolutiondate='2026-08-14T09:00:00.000+0000',
                histories=[self._status_history('2026-08-14T09:00:00.000+0000', 'Open', 'Fixed')],
            ),
            self._jira_issue_payload(
                issue_key='STDEL-9004',
                summary='Open medium bug in second week',
                status='Open',
                resolution=None,
                priority='P3-Medium',
                created='2026-08-11T10:00:00.000+0000',
                updated='2026-08-11T10:00:00.000+0000',
                histories=[],
            ),
        ]

        # When
        call_command(
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start', '2026-08-03',
            '--coverage-end', '2026-08-16',
            stdout=StringIO(),
        )
        run = BugTrendCalculationRun.objects.get(scope=scope, status=BugTrendCalculationRun.STATUS_COMPLETED)
        first_bucket = BugTrendBucket.objects.get(scope=scope, calculation_run=run, bucket_start=date(2026, 8, 3))
        response = self.client.get(reverse('ui_web:bug_trend'), {
            'scope_id': scope.id,
            'begin': '2026-08-03',
            'end': '2026-08-16',
        })
        evidence_response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-16',
            'bucket': str(first_bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
        })
        nonblank_pixels, evidence_text, chart_config = self._render_chart_and_click_evidence(response, evidence_response)

        # Then
        series_values = {dataset['label']: dataset['data'] for dataset in chart_config['data']['datasets']}
        self.assertTrue(nonblank_pixels)
        self.assertEqual(['26WW32', '26WW33'], chart_config['data']['labels'])
        self.assertEqual([1, 2], series_values['all_open_bugs'])
        self.assertEqual([1, 1], series_values['all_open_critical_high'])
        self.assertEqual([1, 1], series_values['new_critical_high'])
        self.assertEqual([1, 1], series_values['new_medium_low'])
        self.assertEqual([-1, -1], series_values['fixed_or_closed_bugs'])
        self.assertTrue(chart_config['options']['plugins']['legend']['display'])
        self.assertEqual('top', chart_config['options']['plugins']['legend']['position'])
        self.assertIn('Fixed Or Closed Bugs', chart_config['legendText'])
        self.assertIn('STDEL-9002', evidence_text)

    def test_shouldRenderChartAndOpenEvidenceFromClickedBucket(self):
        # Given
        _, run, bucket = self._seed_trend_data()
        response = self.client.get(reverse('ui_web:bug_trend'), {'begin': '2026-08-03', 'end': '2026-08-09'})
        evidence_response = self.client.get(reverse('ui_web:bug_trend_evidence'), {
            'scope_id': run.scope_id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'bucket': str(bucket.id),
            'series': 'fixed_or_closed_bugs',
            'chart_id': 'default_bug_trend',
        })
        nonblank_pixels, evidence_text, chart_config = self._render_chart_and_click_evidence(response, evidence_response)

        # Then
        self.assertTrue(nonblank_pixels)
        self.assertIn('fixed_or_closed_bugs tickets for 26WW32', evidence_text)
        self.assertIn('STDEL-8942', evidence_text)
        self.assertIn('run=' + str(run.id), chart_config['evidenceUrl'])
        self.assertIn('series=fixed_or_closed_bugs', chart_config['evidenceUrl'])

    def test_shouldShowUnavailableStateWhenRunCoverageDoesNotCoverSelectedRange(self):
        # Given
        self._seed_trend_data()
        response = self.client.get(reverse('ui_web:bug_trend'), {'begin': '2026-08-01', 'end': '2026-08-09'})
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})

        try:
            # When
            page.set_content(self._browser_html(response.content.decode()), wait_until='domcontentloaded')

            # Then
            self.assertIn('No completed calculation covers the selected range', page.locator('#bug-trend-chart-container').inner_text())
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _seed_trend_data(self):
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 8, 3),
            source_coverage_end=date(2026, 8, 9),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            fixed_or_closed_count=1,
            open_count=1,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-8942',
            summary='Failure in emulation flow',
            issue_type='Bug',
            status='Fixed',
            severity_value='P3-Medium',
            component_value='team_emulation',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='fixed_or_closed_bugs',
            issue_key='STDEL-8942',
            summary='Failure in emulation flow',
            status='Fixed',
            severity_value='P3-Medium',
            component_value='team_emulation',
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        return scope, run, bucket

    def _render_chart_and_click_evidence(self, response, evidence_response):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
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
                    config.legendText = document.getElementById('bugTrendLegend')?.innerText || '';
                    return config;
                }
            """)
            return nonblank_pixels, page.locator('#bug-trend-evidence-container').inner_text(), chart_config
        finally:
            page.close()
            browser.close()
            playwright.stop()

    def _jira_issue_payload(
            self,
            issue_key='STDEL-8942',
            summary='Failure in emulation flow',
            status='Fixed',
            resolution='Fixed',
            priority='P3-Medium',
            created='2026-08-04T10:00:00.000+0000',
            updated='2026-08-05T10:00:00.000+0000',
            resolutiondate='2026-08-05T09:00:00.000+0000',
            histories=None):
        histories = histories if histories is not None else [self._status_history('2026-08-05T09:00:00.000+0000', 'Open', 'Fixed')]
        fields = {
            'summary': summary,
            'issuetype': {'name': 'Bug'},
            'status': {'name': status},
            'resolution': {'name': resolution} if resolution else None,
            'priority': {'name': priority},
            'components': [{'name': 'team_emulation'}],
            'assignee': {'displayName': 'Alice'},
            'created': created,
            'updated': updated,
            'resolutiondate': resolutiondate,
        }
        return {
            'key': issue_key,
            'fields': fields,
            'changelog': {
                'total': len(histories),
                'histories': histories,
            },
        }

    def _status_history(self, changed_at, from_status, to_status):
        return {
            'created': changed_at,
            'items': [
                {'field': 'status', 'fromString': from_status, 'toString': to_status},
            ],
        }

    def _browser_html(self, html):
        html = html.replace(
            '<script src="https://unpkg.com/chart.js@4.5.1/dist/chart.umd.js"></script>',
            '<script>' + self._chart_stub() + '</script>',
        ).replace(
            '<script src="/static/js/vendor_fallbacks.js"></script>',
            '<script>' + self._htmx_stub() + self._chart_stub() + '</script>',
        ).replace(
            '<script src="https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js"></script>',
            '<script>' + self._htmx_stub() + '</script>',
        )
        external_assets = [
            '<link rel="stylesheet" href="https://unpkg.com/bulma@1.0.4/css/bulma.min.css">',
            '<link rel="stylesheet" href="https://unpkg.com/iconoir@7.11.0/css/iconoir.css">',
            '<script src="https://unpkg.com/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>',
            '<script src="https://unpkg.com/chartjs-plugin-annotation@3.1.0/dist/chartjs-plugin-annotation.min.js"></script>',
            '<script src="/static/js/main.js"></script>',
            '<link rel="stylesheet" href="/static/css/main.css">',
        ]
        for asset in external_assets:
            html = html.replace(asset, '')
        return html

    def _chart_stub(self):
        return """
            window.Chart = function(context, config) {
                this.config = config;
                context.fillStyle = '#f2c94c';
                context.fillRect(20, 20, 160, 80);
                context.canvas.addEventListener('click', function(event) {
                    if (config.options && config.options.onClick) {
                        config.options.onClick(event, [{ index: 0, datasetIndex: 4 }]);
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
