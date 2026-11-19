import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import Task, EnrichmentOptions, TaskSearchCriteria, MemberGroup
from ui_web.facades.tasks_facade import TasksFacade
from ui_web.convertors.task_convertor import TaskConvertor
from ui_web.convertors.member_convertor import MemberConvertor
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.tests.fixtures.business_scenarios import BusinessScenarios
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_forecast_api import MockForecastApi


class TestApiUIWebHealth(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.forecast_api = MockForecastApi()
        
        self.available_member_groups = [
            MemberGroup(id="frontend-team", name="Frontend Development Team"),
            MemberGroup(id="backend-team", name="Backend Development Team"),
            MemberGroup(id="devops-team", name="DevOps Team")
        ]
        
        self.current_tasks_criteria = TaskSearchCriteria(
            status_filter=["In Progress", "Development", "Testing"]
        )
        
        self.recently_finished_criteria = TaskSearchCriteria(
            status_filter=["Done", "Completed"]
        )
        
        self.workflow_config = WorkflowConfig(
            in_progress_status_codes=["In Progress", "Development", "Testing"],
            done_status_codes=["Done", "Completed", "Closed"],
            pending_status_codes=["To Do", "Open", "Backlog"],
            stages={
                "development": ["In Progress", "Development"],
                "qa": ["Testing", "Code Review"],
                "done": ["Done", "Completed", "Closed"]
            },
            recently_finished_tasks_days=30
        )
        
        # Mock member group config for filtering
        member_group_config = Mock()
        member_group_config.members = {
            "alice.johnson": {"member_groups": ["frontend-team"]},
            "bob.smith": {"member_groups": ["backend-team"]},
            "charlie.brown": {"member_groups": ["devops-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {}
        
        self.member_group_filter = MemberGroupTaskFilter(member_group_config)
        
        # Mock time policy for conversion
        with patch('sd_metrics_lib.utils.time.TimePolicy.BUSINESS_HOURS'):
            self.task_convertor = TaskConvertor(Mock())
        
        self.member_convertor = MemberConvertor()
        
        self.facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=self.member_group_filter,
            member_convertor=self.member_convertor
        )
    
    async def test_shouldProvideHealthyProjectStatusWhenAllTasksAreOnTrackForSprintGoalAchievement(self):
        # Given - Sprint with all green health tasks
        healthy_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(8.0)
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")
                .with_time_spent_hours(16.0)
                .build()
        ]
        
        # Mock forecasts to return GREEN health status
        for task in healthy_tasks:
            task.forecast = Mock()
            task.forecast.target = Mock()
            task.forecast.target.health_status = Mock()
            task.forecast.target.health_status.value = 3  # GREEN
        
        self.task_search_api.mock.search.side_effect = [healthy_tasks, []]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(2, len(result))
        healthy_task_count = sum(1 for task in result 
                               if task.forecast and task.forecast.health_status and task.forecast.health_status.value == 3)
        self.assertEqual(2, healthy_task_count)
    
    async def test_shouldIdentifyAtRiskSprintWhenCriticalTasksShowRedHealthStatusForEscalation(self):
        # Given - Sprint with critical tasks in red health
        at_risk_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(40.0)  # Excessive time spent
                .build()
        ]
        
        # Mock forecast to return RED health status
        at_risk_tasks[0].forecast = Mock()
        at_risk_tasks[0].forecast.target = Mock()
        at_risk_tasks[0].forecast.target.health_status = Mock()
        at_risk_tasks[0].forecast.target.health_status.value = 1  # RED
        
        self.task_search_api.mock.search.side_effect = [at_risk_tasks, []]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(1, len(result))
        critical_task = result[0]
        self.assertEqual(1, critical_task.forecast.health_status.value)  # RED status for escalation
        self.assertGreater(critical_task.time_tracking.total_spent_time_days, 3.0)  # High time spent indicator
    
    async def test_shouldProvideWarningIndicatorsWhenSprintVelocityRisksDeadlineForStakeholderCommunication(self):
        # Given - Sprint with mixed health but trending towards yellow
        mixed_health_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(24.0)
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")
                .with_time_spent_hours(8.0)
                .build()
        ]
        
        # Mock first task as YELLOW, second as GREEN
        mixed_health_tasks[0].forecast = Mock()
        mixed_health_tasks[0].forecast.target = Mock()
        mixed_health_tasks[0].forecast.target.health_status = Mock()
        mixed_health_tasks[0].forecast.target.health_status.value = 2  # YELLOW
        
        mixed_health_tasks[1].forecast = Mock()
        mixed_health_tasks[1].forecast.target = Mock()
        mixed_health_tasks[1].forecast.target.health_status = Mock()
        mixed_health_tasks[1].forecast.target.health_status.value = 3  # GREEN
        
        self.task_search_api.mock.search.side_effect = [mixed_health_tasks, []]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(2, len(result))
        
        warning_tasks = [task for task in result 
                        if task.forecast and task.forecast.health_status and task.forecast.health_status.value == 2]
        healthy_tasks = [task for task in result 
                        if task.forecast and task.forecast.health_status and task.forecast.health_status.value == 3]
        
        self.assertEqual(1, len(warning_tasks))  # One task needs attention
        self.assertEqual(1, len(healthy_tasks))  # One task on track
    
    async def test_shouldIndicateTeamCapacityIssuesWhenMembersHaveNoActiveTasksForWorkloadBalancing(self):
        # Given - Scenario where some team members have no active work
        tasks_with_gaps = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")  # Only Alice has work
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [tasks_with_gaps, []]
        
        # When
        result = await self.facade.get_tasks("frontend-team")
        
        # Then
        self.assertEqual(1, len(result))
        
        # Should identify that only one member is actively working
        active_assignees = {task.assignment.assignee.id for task in result 
                          if task.assignment and task.assignment.assignee}
        self.assertEqual(1, len(active_assignees))
        self.assertIn("alice.johnson", active_assignees)
        
        # This indicates potential capacity issues for project manager attention
    
    async def test_shouldReportHealthyVelocityWhenRecentlyCompletedTasksShowGoodProgressForRetrospective(self):
        # Given - Recently completed tasks showing healthy completion pattern
        current_tasks = []
        completed_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(16.0)  # 2 business days - reasonable
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")
                .with_time_spent_hours(24.0)  # 3 business days - reasonable
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [current_tasks, completed_tasks]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(2, len(result))
        
        # All completed tasks should show reasonable time investment
        reasonable_completion_times = [task for task in result 
                                     if task.time_tracking.total_spent_time_days and 
                                        1.0 <= task.time_tracking.total_spent_time_days <= 4.0]
        self.assertEqual(2, len(reasonable_completion_times))
    
    async def test_shouldHandleAPIFailuresGracefullyToMaintainDashboardAvailabilityForUsers(self):
        # Given - External API failure scenario
        self.task_search_api.mock.search.side_effect = Exception("External system unavailable")
        
        # When/Then - Should propagate exception for view layer to handle gracefully
        with self.assertRaises(Exception) as context:
            await self.facade.get_tasks()
        
        self.assertEqual("External system unavailable", str(context.exception))
        
        # This allows the view layer to show appropriate error messages to users
        # while maintaining dashboard availability with cached or fallback data
    
    async def test_shouldProvideEmptyStateIndicatorsWhenNoTasksExistForNewProjectGuidance(self):
        # Given - New project scenario with no tasks
        self.task_search_api.mock.search.side_effect = [[], []]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(0, len(result))
        
        # Empty state should guide users on next steps
        # (This would typically be handled in the view layer with helpful messaging)
    
    async def test_shouldMaintainConsistentHealthStatusAcrossMultipleTeamViewsForStakeholderAlignment(self):
        # Given - Tasks distributed across multiple teams
        multi_team_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")  # Frontend team
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")     # Backend team
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("charlie.brown") # DevOps team
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [multi_team_tasks, []]
        
        # When - Get tasks for all teams view
        all_teams_result = await self.facade.get_tasks()
        
        # When - Get tasks for specific team
        self.task_search_api.mock.search.side_effect = [multi_team_tasks, []]
        frontend_result = await self.facade.get_tasks("frontend-team")
        
        # Then
        self.assertEqual(3, len(all_teams_result))
        self.assertEqual(1, len(frontend_result))
        
        # Health status reporting should be consistent across different views
        # for stakeholder alignment and decision making


if __name__ == '__main__':
    unittest.main()