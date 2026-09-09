import json
from contextlib import ExitStack
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from forecast.app.domain.model.enums import TaskScope
from playwright.sync_api import sync_playwright
from sd_metrics_lib.utils.enums import HealthStatus

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendBucketIssue,
    BugTrendCalculationRun,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
    ProviderProfileConfig,
)
from ui_web.data.member_data import MemberGroupData
from ui_web.data.pull_request_data import (
    ApprovalData,
    LinkedTaskData,
    PersonActivitySummaryData,
    PullRequestData,
)
from ui_web.data.task_data import (
    AssigneeData,
    AssignmentData,
    ForecastData,
    LinkedPullRequestData,
    ReleaseData,
    SystemMetadataData,
    TaskData,
    TimeTrackingData,
)
from ui_web.data.task_forecast_data import (
    TaskForecastBreakdownItem,
    TaskForecastParamsData,
    TaskForecastRequestData,
    TaskForecastSummaryData,
)
from ui_web.data.velocity_threshold_data import VelocityThresholdsData
from ui_web.data.velocity_task_detail_data import DeveloperVelocitySummary, TaskVelocityData


class TestUiDesignBaselineGate(TestCase):
    def test_shouldDocumentAndEnforceSharedUiContracts(self):
        project_root = Path(__file__).resolve().parents[2]
        template_root = project_root / 'ui_web' / 'templates'
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        audit_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / '2026-09-08-ui-baseline-audit.md'

        overlay = overlay_path.read_text(encoding='utf-8')
        audit = audit_path.read_text(encoding='utf-8')
        self.assertIn('ui_web.tests.test_ui_design_baseline_gate', overlay)
        self.assertIn('Provider Setup inventory and Provider Profile Config editor', audit)
        self.assertIn('Monkey-user flow', audit)
        self.assertIn('Current Tasks', audit)
        self.assertIn('Pull Requests', audit)
        self.assertIn('Task Forecast', audit)

        dirty_templates = [
            path
            for path in template_root.rglob('*.html')
            if 'data-dirty-form' in path.read_text(encoding='utf-8')
        ]
        self.assertEqual(
            {
                template_root / 'bug_trend_scope_config.html',
                template_root / 'partials' / 'provider_profile_editor.html',
            },
            set(dirty_templates),
        )
        state_partial = (template_root / 'partials' / 'dashboard_editor_state_banners.html').read_text(encoding='utf-8')
        self.assertIn('dashboard-unsaved-banner', state_partial)
        self.assertIn('dashboard-validation-banner', state_partial)
        for path in dirty_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-edit-form', content, str(path))
            self.assertIn('data-required-form', content, str(path))
            self.assertIn('partials/dashboard_editor_state_banners.html', content, str(path))
            self.assertIn('dashboard-action-bar', content, str(path))
            self.assertIn('dashboard-action-group', content, str(path))

        css = (project_root / 'ui_web' / 'static' / 'css' / 'main.css').read_text(encoding='utf-8')
        for color in ['green', 'blue', 'purple']:
            self.assertIn(f'is-provider-{color}', css)

        for path in [
            template_root / 'bug_trend_scope_config.html',
            template_root / 'partials' / 'provider_profile_editor.html',
        ]:
            content = path.read_text(encoding='utf-8')
            self.assertIn('provider-tab-shell', content, str(path))
            self.assertIn('scope-provider-choice', content, str(path))
            self.assertIn('provider-tab-check', content, str(path))
            self.assertIn('role="tablist"', content, str(path))
            self.assertIn('role="tabpanel"', content, str(path))
            self.assertIn('is-provider-{{', content, str(path))

        for path in [
            template_root / 'partials' / 'current_tasks_filters.html',
            template_root / 'partials' / 'pull_request_filters.html',
            template_root / 'partials' / 'bug_trend_content.html',
            template_root / 'partials' / 'bug_trend_evidence.html',
        ]:
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('data-dirty-form', content, str(path))
            self.assertNotIn('dashboard-action-bar', content, str(path))

    def test_shouldKeepCoreUiSurfacesWithinBaselineAtDesktopAndPhone(self):
        scope, _, _ = self._seed_bound_scope_with_run()
        responses = [
            ('provider_setup_inventory', self.client.get(reverse('ui_web:provider_setup')), {'table': True}),
            (
                'bug_trend',
                self.client.get(reverse('ui_web:bug_trend'), {
                    'scope_id': scope.id,
                    'begin': '2026-09-01',
                    'end': '2026-09-07',
                    'chart_id': 'default_bug_trend',
                }),
                {'tool_form': True},
            ),
            ('task_forecast', self.client.get(reverse('ui_web:task_forecast')), {'tool_form': True}),
            (
                'ai_dashboard_workflow',
                self.client.get(reverse('ui_web:ai_dashboard_workflow')),
                {'tool_form': True, 'table': True},
            ),
            (
                'provider_profile_jira_editor',
                self.client.get(reverse('ui_web:provider_setup'), {'mode': 'new', 'provider_id': 'jira'}),
                {'editor': True, 'provider_tabs': True},
            ),
            (
                'provider_profile_hsdes_editor',
                self.client.get(reverse('ui_web:provider_setup'), {'mode': 'new', 'provider_id': 'hsdes'}),
                {'editor': True, 'provider_tabs': True},
            ),
            (
                'scope_config_hsdes_editor',
                self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                    'mode': 'new',
                    'provider_id': 'hsdes',
                    'profile_id': 'nvu-ttl-hsdes',
                }),
                {'editor': True, 'provider_tabs': True},
            ),
            ('scope_library', self.client.get(reverse('ui_web:bug_trend_scope_library')), {'table': True}),
            ('data_health', self.client.get(reverse('ui_web:data_health')), {'table': True}),
            (
                'workbench',
                self.client.get(reverse('ui_web:workbench'), {
                    'scope_id': scope.id,
                    'begin': '2026-09-01',
                    'end': '2026-09-07',
                    'chart_id': 'default_bug_trend',
                }),
                {'tool_form': True},
            ),
        ]

        for label, response, _ in responses:
            self.assertEqual(200, response.status_code, label)

        results = self._measure_baseline_pages([
            (label, response.content.decode(), expectations)
            for label, response, expectations in responses
        ])

        for label, viewport_results in results.items():
            for viewport, metrics in viewport_results.items():
                self.assertFalse(metrics['page_horizontal_overflow'], f'{label} {viewport}')
                self.assertEqual([], metrics['clipped_action_buttons'], f'{label} {viewport}')
                self.assertGreater(metrics['visible_button_count'], 0, f'{label} {viewport}')
                self.assertEqual([], metrics['table_contract_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['table_density_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['table_button_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['button_metric_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['form_metric_failures'], f'{label} {viewport}')
                if metrics['expects_table']:
                    self.assertGreater(metrics['responsive_table_count'], 0, f'{label} {viewport}')
                if metrics['expects_dense_table']:
                    self.assertGreater(metrics['dense_table_count'], 0, f'{label} {viewport}')
                    self.assertLessEqual(metrics['dense_table_max_row_height'], 72, f'{label} {viewport}')
                    self.assertLessEqual(metrics['dense_table_button_height_delta'], 1, f'{label} {viewport}')
                if metrics['expects_tool_form']:
                    self.assertGreater(metrics['tool_form_count'], 0, f'{label} {viewport}')
                    self.assertGreater(metrics['tool_grid_count'], 0, f'{label} {viewport}')
                    self.assertEqual(0, metrics['tool_form_dirty_count'], f'{label} {viewport}')
                    self.assertLessEqual(metrics['tool_form_button_height_delta'], 1, f'{label} {viewport}')
                    self.assertLessEqual(metrics['tool_form_control_height_delta'], 1, f'{label} {viewport}')
                if metrics['expects_editor']:
                    self.assertEqual(1, metrics['required_summary_count'], f'{label} {viewport}')
                    self.assertEqual(1, metrics['dirty_banner_count'], f'{label} {viewport}')
                    self.assertGreater(metrics['action_bar_count'], 0, f'{label} {viewport}')
                    self.assertLessEqual(metrics['action_bar_button_height_delta'], 1, f'{label} {viewport}')
                    self.assertLessEqual(metrics['editor_control_height_delta'], 1, f'{label} {viewport}')
                if metrics['expects_provider_tabs']:
                    self.assertGreater(metrics['provider_tab_shell_count'], 0, f'{label} {viewport}')
                    self.assertTrue(metrics['selected_provider_check_visible'], f'{label} {viewport}')

    def test_shouldKeepDenseDashboardTablesWithinBrowserMetrics(self):
        pages = [
            ('current_tasks_dense_table', self._dense_current_tasks_html(), {'dense_table': True}),
            ('pull_requests_dense_tables', self._dense_pull_requests_html(), {'dense_table': True}),
            ('task_forecast_dense_table', self._dense_task_forecast_html(), {'dense_table': True}),
            ('velocity_task_dense_table', self._dense_velocity_task_html(), {'dense_table': True}),
        ]

        results = self._measure_baseline_pages(pages)

        for label, viewport_results in results.items():
            for viewport, metrics in viewport_results.items():
                self.assertFalse(metrics['page_horizontal_overflow'], f'{label} {viewport}')
                self.assertEqual([], metrics['table_contract_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['table_density_failures'], f'{label} {viewport}')
                self.assertEqual([], metrics['table_button_failures'], f'{label} {viewport}')
                self.assertGreater(metrics['dense_table_count'], 0, f'{label} {viewport}')
                self.assertLessEqual(metrics['dense_table_max_row_height'], 72, f'{label} {viewport}')
                self.assertLessEqual(metrics['dense_table_button_height_delta'], 1, f'{label} {viewport}')

    def test_shouldRunVisualRegressionManifestAgainstCoreRoutes(self):
        scope, run, bucket = self._seed_bound_scope_with_run()
        project_root = Path(__file__).resolve().parents[2]
        manifest_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'visual-regression' / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest_routes = {item['route'] for item in manifest['capturePlan']}
        self.assertTrue({
            '/current-tasks/',
            '/pull-requests/',
            '/task-forecast/',
            '/team-velocity/',
            '/dev-velocity/',
        }.issubset(manifest_routes))
        for item in manifest['capturePlan']:
            if item['route'] in {'/team-velocity/', '/dev-velocity/'}:
                self.assertIn('chart-drilldown-selected', item['stateTargets'])
                self.assertIn('table-density', item['stateTargets'])
                self.assertTrue(any(scenario.get('requiresHook') for scenario in item['stateScenarios']))
            if item['route'] == '/provider-setup/':
                scenarios = {scenario['name']: scenario for scenario in item['stateScenarios']}
                self.assertIn('profile-required-missing', scenarios)
                self.assertIn('profile-dirty-unsaved', scenarios)
                self.assertIn('required-summary-visible', scenarios['profile-required-missing']['checks'])
            if item['route'] == '/bug-trend/scope-config/':
                scenarios = {scenario['name']: scenario for scenario in item['stateScenarios']}
                self.assertIn('scope-required-missing', scenarios)
                self.assertIn('scope-dirty-unsaved', scenarios)
                self.assertIn('dirty-banner-visible', scenarios['scope-dirty-unsaved']['checks'])
        pages = []

        with self._visual_manifest_page_fakes():
            for capture in manifest['capturePlan']:
                response = self.client.get(
                    capture['route'],
                    self._visual_manifest_params(capture['route'], scope, run, bucket),
                )
                self.assertEqual(200, response.status_code, capture['route'])
                pages.append((capture['name'], response.content.decode()))

        results = self._measure_visual_manifest_pages(pages, manifest['viewports'])

        for label, viewport_results in results.items():
            for viewport, metrics in viewport_results.items():
                self.assertFalse(metrics['page_horizontal_overflow'], f'{label} {viewport}')
                self.assertEqual([], metrics['clipped_buttons'], f'{label} {viewport}')
                self.assertEqual([], metrics['unnamed_icon_buttons'], f'{label} {viewport}')

    def _visual_manifest_params(self, route, scope, run, bucket):
        if route == '/bug-trend/scope-config/':
            return {'scope_id': scope.id}
        if route == '/workbench/':
            return {
                'scope_id': scope.id,
                'begin': '2026-09-01',
                'end': '2026-09-07',
                'chart_id': 'default_bug_trend',
                'run': str(run.id),
                'bucket': str(bucket.id),
                'series': 'new_critical_high',
            }
        if route == '/task-forecast/':
            return {'task_id': 'TASK-101', 'include_done_tasks': 'true'}
        if route == '/bug-trend/scope-audit/':
            return {'scope_id': scope.id}
        if route == '/partials/bug-trend/evidence/':
            return {
                'scope_id': scope.id,
                'begin': '2026-09-01',
                'end': '2026-09-07',
                'run': str(run.id),
                'bucket': str(bucket.id),
                'series': 'new_critical_high',
                'chart_id': 'default_bug_trend',
            }
        return {}

    def _dense_current_tasks_html(self):
        return self._fragment_html(render_to_string('partials/task_table.html', {
            'tasks': [self._current_task_data()],
            'show_header': True,
            'pr_gateway_column_enabled': True,
            'release_column_enabled': True,
            'task_table_colspan': 11,
        }))

    def _dense_pull_requests_html(self):
        summary = [
            PersonActivitySummaryData('Monkey User', created_count=1, approved_count=0, changes_requested_count=0),
            PersonActivitySummaryData('Lead Reviewer', created_count=0, approved_count=1, changes_requested_count=0),
        ]
        return self._fragment_html(
            render_to_string('partials/pull_request_summary_table.html', {'activity_summary': summary})
            + render_to_string('partials/pull_requests_table.html', {'pull_requests': [self._pull_request_data()]})
        )

    def _dense_task_forecast_html(self):
        return self._fragment_html(render_to_string('partials/task_forecast_content.html', {
            'success': True,
            'task_forecast': self._task_forecast_summary_data(),
            'chart_data': '',
            'include_done_tasks': True,
            'time_unit': 'days',
            'forecast_params': TaskForecastParamsData(task_id='TASK-101', task_scope=TaskScope.ALL),
        }))

    def _dense_velocity_task_html(self):
        return self._fragment_html(render_to_string('partials/velocity_task_table.html', {
            'tasks': [self._velocity_task_data()],
            'summary': DeveloperVelocitySummary(
                total_story_points=3.0,
                total_time_days=1.0,
                velocity=3.0,
                total_task_story_points=5.0,
                total_estimated_days=2.0,
                average_deviation_percent=0.0,
                working_days=1.0,
                working_days_in_month=22,
                workload_percent=4.5,
            ),
        }))

    def _current_task_data(self):
        group = MemberGroupData('core', 'Core Team')
        return TaskData(
            id='TASK-101',
            title='Tighten dense dashboard table behavior',
            assignment=AssignmentData(AssigneeData('user-1', 'Monkey User'), group),
            time_tracking=TimeTrackingData(total_spent_time_days=1.5, current_assignee_spent_time_days=0.8),
            system_metadata=SystemMetadataData('In Progress', 'https://provider.example.test/TASK-101'),
            story_points=5,
            child_tasks_count=2,
            stage='Development',
            iteration='Sprint 12',
            forecast=ForecastData(HealthStatus.GREEN, estimation_time_days=2.5),
            releases=[ReleaseData('rel-1', '2026.015')],
            linked_pull_request=LinkedPullRequestData(
                id='101',
                repository_id='repo-1',
                project_id='project-1',
                project_name='Metrics',
                url='https://provider.example.test/pr/101',
            ),
        )

    def _velocity_task_data(self):
        task = self._current_task_data()
        return TaskVelocityData(
            id=task.id,
            title=task.title,
            assignment=task.assignment,
            time_tracking=task.time_tracking,
            system_metadata=task.system_metadata,
            story_points=task.story_points,
            priority=task.priority,
            child_tasks=task.child_tasks,
            child_tasks_count=task.child_tasks_count,
            parent=task.parent,
            stage=task.stage,
            iteration=task.iteration,
            forecast=task.forecast,
            releases=task.releases,
            custom_sort_fields=task.custom_sort_fields,
            linked_pull_request=task.linked_pull_request,
            developer_story_points=3.0,
            developer_time_days=1.0,
            total_estimated_days=2.0,
            estimated_days=1.2,
            deviation_percent=0.0,
        )

    def _pull_request_data(self):
        release = ReleaseData('rel-1', '2026.015')
        return PullRequestData(
            id='101',
            title='Align dense table action controls',
            author_name='Monkey User',
            status='active',
            internal_gate=True,
            url='https://provider.example.test/pr/101',
            repository='metrics',
            repository_id='repo-1',
            project_id='project-1',
            project_name='Metrics',
            approvals=[
                ApprovalData('Lead Reviewer', 'approved', 'main', True),
                ApprovalData('Dev Reviewer', 'waiting', 'additional', False),
            ],
            linked_task=LinkedTaskData(
                id='TASK-101',
                url='https://provider.example.test/TASK-101',
                status='Code Review',
                iteration='Sprint 12',
                releases=[release],
            ),
        )

    def _task_forecast_summary_data(self):
        task_forecasts = [
            TaskForecastBreakdownItem('TASK-101', 'Forecast root task', 5.0, 0, True, False, 'In Progress'),
            TaskForecastBreakdownItem('TASK-102', 'Child implementation task', 3.0, 1, False, False, 'Development'),
            TaskForecastBreakdownItem('TASK-103', 'Completed verification task', 1.0, 1, False, True, 'Done'),
        ]
        return TaskForecastSummaryData(
            task_title='SUMMARY',
            total_estimation_days=9.0,
            forecasted_start_date=datetime(2026, 9, 9, tzinfo=timezone.utc),
            forecasted_end_date=datetime(2026, 9, 18, tzinfo=timezone.utc),
            average_team_velocity=1.2,
            task_forecasts=task_forecasts,
            completed_estimation_days=1.0,
            remaining_estimation_days=8.0,
        )

    def _visual_manifest_page_fakes(self):
        class FakeFilterPanel:
            has_active_selection = False

        class FakeTaskFilterFacade:
            @staticmethod
            def parse_selections(_query):
                return {}

            @staticmethod
            def requires_full_fetch(_selections):
                return False

            @staticmethod
            def get_panel(_tasks, _selections):
                return FakeFilterPanel()

            @staticmethod
            def filter_tasks(tasks, _selections):
                return tasks

        class FakeTasksFacade:
            @staticmethod
            def is_lazy_loading_enabled():
                return False

            @staticmethod
            def is_release_column_enabled():
                return True

            @staticmethod
            def is_pull_request_gateway_column_enabled():
                return True

            @staticmethod
            def task_table_colspan():
                return 11

            async def get_tasks(self, _group_id):
                return [self_task._current_task_data()]

        class FakeMembersFacade:
            @staticmethod
            async def get_available_members(_tasks, _group_id):
                return []

        class FakeCurrentTasksContainer:
            tasks_facade = FakeTasksFacade()
            task_filter_facade = FakeTaskFilterFacade()
            members_facade = FakeMembersFacade()

        class FakePullRequestsFacade:
            @staticmethod
            def is_pull_requests_enabled():
                return True

            async def get_pull_requests(self, _member_group_id):
                return [self_task._pull_request_data()]

        class FakePullRequestsContainer:
            pull_requests_facade = FakePullRequestsFacade()

        class FakeTaskForecastConvertor:
            @staticmethod
            def extract_request_data_from_request(request):
                return TaskForecastRequestData(
                    task_id=request.GET.get('task_id', 'TASK-101'),
                    task_scope=TaskScope.ALL if request.GET.get('include_done_tasks') == 'true' else TaskScope.ACTIVE_ONLY,
                )

        class FakeTaskForecastFacade:
            @staticmethod
            async def get_forecast_params_data(request_data):
                return TaskForecastParamsData(task_id=request_data.task_id, task_scope=request_data.task_scope)

            @staticmethod
            async def get_task_forecast_hierarchy_data(_request_data):
                return []

            @staticmethod
            def get_forecast_chart_from_data(_task_hierarchy):
                return None

            @staticmethod
            def get_forecast_summary_from_data(_task_hierarchy):
                return self_task._task_forecast_summary_data()

        class FakeTaskForecastContainer:
            task_forecast_facade = FakeTaskForecastFacade()
            task_forecast_convertor = FakeTaskForecastConvertor()

        class FakeVelocityFacade:
            @staticmethod
            def has_custom_filter(_member_group_id):
                return False

            @staticmethod
            def get_velocity_thresholds():
                return VelocityThresholdsData([])

            @staticmethod
            async def get_velocity_reports_data(*_args):
                return []

            @staticmethod
            def get_velocity_chart_data(*_args):
                return None

            @staticmethod
            def get_story_points_chart_data(*_args):
                return None

        class FakeTeamVelocityContainer:
            team_velocity_facade = FakeVelocityFacade()

        class FakeDevVelocityContainer:
            dev_velocity_facade = FakeVelocityFacade()

        self_task = self
        stack = ExitStack()
        stack.enter_context(patch.multiple(
            'ui_web.views.current_tasks_view',
            ui_web_container=FakeCurrentTasksContainer(),
        ))
        stack.enter_context(patch.multiple(
            'ui_web.views.pull_requests_view',
            ui_web_container=FakePullRequestsContainer(),
        ))
        stack.enter_context(patch.multiple(
            'ui_web.views.task_forecast_view',
            ui_web_container=FakeTaskForecastContainer(),
        ))
        stack.enter_context(patch.multiple(
            'ui_web.views.team_velocity_view',
            ui_web_container=FakeTeamVelocityContainer(),
        ))
        stack.enter_context(patch.multiple(
            'ui_web.views.dev_velocity_view',
            ui_web_container=FakeDevVelocityContainer(),
        ))
        return stack

    @staticmethod
    def _fragment_html(fragment):
        return (
            '<!doctype html><html lang="en" data-theme="dark" class="has-navbar-fixed-top">'
            '<head></head>'
            '<body class="is-flex is-flex-direction-column is-fullheight">'
            '<div class="columns is-gapless is-flex-grow-1 dashboard-app-layout">'
            '<main class="column is-flex is-flex-direction-column dashboard-main-column">'
            '<section class="section is-flex-grow-1"><div class="container"><div id="main-content">'
            f'{fragment}'
            '</div></div></section>'
            '</main></div></body></html>'
        )

    def test_shouldSupportMonkeyUserProviderProfileScopeWorkbenchJourney(self):
        new_jira_page = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'jira',
        })
        self.assertIn('id="provider-profile-id" name="profile_id" value=""', new_jira_page.content.decode())
        self.assertIn('provider-setup-choice is-provider-green is-selected', new_jira_page.content.decode())
        profile_required_state = self._measure_required_submit(
            new_jira_page.content.decode(),
            'button[name="action"][value="test_connection"]',
        )
        self.assertIn('connection_base_url', profile_required_state['invalid_field_names'])
        self.assertEqual(
            len(profile_required_state['invalid_field_names']),
            profile_required_state['invalid_aria_count'],
        )
        self.assertGreater(profile_required_state['missing_shell_count'], 0)
        self.assertTrue(profile_required_state['summary_visible'])

        jira_payload = self._jira_profile_payload('monkey-jira-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.create_jira_client') as create_jira_client:
            create_jira_client.return_value.get_server_info.return_value = {
                'serverTitle': 'Monkey Jira',
                'version': '10.0',
            }
            test_response = self.client.post(reverse('ui_web:provider_setup'), {
                **jira_payload,
                'action': 'test_connection',
                'connection_api_token': 'secret-jira-token',
            })
        self.assertEqual(200, test_response.status_code)
        test_content = test_response.content.decode()
        self.assertIn('Connection test: success', test_content)
        self.assertIn('Jira connection succeeded.', test_content)
        self.assertNotIn('secret-jira-token', test_content)

        save_profile_response = self.client.post(reverse('ui_web:provider_setup'), jira_payload, follow=True)
        jira_profile = ProviderProfileConfig.objects.get(profile_id='monkey-jira-profile')
        self.assertEqual(200, save_profile_response.status_code)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_ENABLED, jira_profile.lifecycle_state)

        hsdes_payload = self._hsdes_profile_payload('monkey-hsdes-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.HsdesHttpClient') as hsdes_client:
            hsdes_client.return_value.execute_saved_query.return_value = {'total': 1, 'data': [{'id': '1'}]}
            hsdes_response = self.client.post(reverse('ui_web:provider_setup'), {
                **hsdes_payload,
                'action': 'test_connection',
            })
        hsdes_content = hsdes_response.content.decode()
        self.assertEqual(200, hsdes_response.status_code)
        self.assertIn('HSD-ES Connection Probe', hsdes_content)
        self.assertIn('value="15017652869"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.tenant"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.bug"', hsdes_content)
        self.assertIn('HSD-ES saved-query probe succeeded.', hsdes_content)
        self.assertNotIn('Advanced source settings', hsdes_content)

        self.client.post(reverse('ui_web:provider_setup'), hsdes_payload, follow=True)
        self.assertEqual(
            ProviderProfileConfig.LIFECYCLE_ENABLED,
            ProviderProfileConfig.objects.get(profile_id='monkey-hsdes-profile').lifecycle_state,
        )

        hsdes_scope_page = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
            'profile_id': 'monkey-hsdes-profile',
        })
        hsdes_scope_content = hsdes_scope_page.content.decode()
        self.assertEqual(200, hsdes_scope_page.status_code)
        self.assertIn('option value="monkey-hsdes-profile" selected', hsdes_scope_content)
        self.assertIn('scope-provider-choice is-provider-blue is-selected', hsdes_scope_content)

        scope_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'jira',
            'profile_id': 'monkey-jira-profile',
        })
        scope_content = scope_response.content.decode()
        self.assertEqual(200, scope_response.status_code)
        self.assertIn('option value="monkey-jira-profile" selected', scope_content)
        self.assertIn('scope-provider-choice is-provider-green is-selected', scope_content)
        scope_required_state = self._measure_required_submit(
            scope_content,
            'button[name="action"][value="save_enable"]',
        )
        self.assertIn('critical_high_values', scope_required_state['invalid_field_names'])
        self.assertIn('open_status_values', scope_required_state['invalid_field_names'])
        self.assertEqual(
            len(scope_required_state['invalid_field_names']),
            scope_required_state['invalid_aria_count'],
        )
        self.assertGreater(scope_required_state['missing_shell_count'], 0)
        self.assertTrue(scope_required_state['summary_visible'])

        save_scope_response = self.client.post(
            reverse('ui_web:bug_trend_scope_config'),
            self._scope_payload('Monkey Jira Scope', 'monkey-jira-profile'),
            follow=True,
        )
        scope = JiraScopeConfig.objects.get(name='Monkey Jira Scope')
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(200, save_scope_response.status_code)
        self.assertTrue(scope.enabled)
        self.assertEqual('monkey-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)

        run, bucket = self._seed_run_and_issue(scope)
        workbench_response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-09-01',
            'end': '2026-09-07',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })
        workbench_content = workbench_response.content.decode()
        self.assertEqual(200, workbench_response.status_code)
        self.assertIn('id="workbench-profile" value="monkey-jira-profile"', workbench_content)
        self.assertIn('id="workbench-provider" value="jira"', workbench_content)
        self.assertIn('MONKEY-1', workbench_content)
        self.assertIn('data-workbench-evidence-workspace', workbench_content)

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
