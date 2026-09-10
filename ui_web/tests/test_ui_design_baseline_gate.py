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


from ui_web.tests.ui_design_browser_metrics_support import UiDesignBrowserMetricsSupport


class TestUiDesignBaselineGate(UiDesignBrowserMetricsSupport, TestCase):
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
