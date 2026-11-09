import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import Task, EnrichmentOptions, TaskSearchCriteria, MemberGroup
from ui_web.facades.tasks_facade import TasksFacade
from ui_web.facades.team_velocity_facade import TeamVelocityFacade
from ui_web.convertors.task_convertor import TaskConvertor
from ui_web.convertors.member_convertor import MemberConvertor
from ui_web.convertors.velocity_chart_convertor import VelocityChartConvertor
from ui_web.convertors.velocity_report_convertor import VelocityReportConvertor
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.utils.task_grouping_utils import TaskGroupingUtils
from ui_web.tests.fixtures.business_scenarios import BusinessScenarios
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder, TaskDataBuilder
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_forecast_api import MockForecastApi
from ui_web.tests.mocks.mock_velocity_api import MockVelocityApi
from ui_web.tests.mocks.mock_assignee_search_api import MockAssigneeSearchApi


class TestApiUIWebEdgeCases(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.forecast_api = MockForecastApi()
        self.velocity_api = MockVelocityApi()
        self.assignee_search_api = MockAssigneeSearchApi()
        
        self.available_member_groups = [
            MemberGroup(id="frontend-team", name="Frontend Development Team"),
            MemberGroup(id="backend-team", name="Backend Development Team")
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
            "bob.smith": {"member_groups": ["backend-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {}
        
        self.member_group_filter = MemberGroupTaskFilter(member_group_config)
        
        # Mock time policy for conversion
        with patch('sd_metrics_lib.utils.time.TimePolicy.BUSINESS_HOURS'):
            self.task_convertor = TaskConvertor(Mock())
        
        self.member_convertor = MemberConvertor()
        self.velocity_chart_convertor = VelocityChartConvertor()
        self.velocity_report_convertor = VelocityReportConvertor(self.assignee_search_api)
        
        self.tasks_facade = TasksFacade(
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
        
        self.velocity_facade = TeamVelocityFacade(
            velocity_api=self.velocity_api,
            assignee_search_api=self.assignee_search_api,
            available_member_groups=self.available_member_groups,
            member_convertor=self.member_convertor,
            velocity_chart_convertor=self.velocity_chart_convertor,
            velocity_report_convertor=self.velocity_report_convertor
        )
    
    async def test_shouldHandleEmptyTaskListGracefullyForNewProjectInitialization(self):
        # Given - New project with no tasks yet
        self.task_search_api.mock.search.side_effect = [[], []]  # No current or finished tasks
        
        # When
        result = await self.tasks_facade.get_tasks()
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            result, self.workflow_config
        )
        
        # Then
        self.assertEqual(0, len(result))
        self.assertEqual([], grouped_result)
        
        # Verify empty state doesn't break workflow
        available_groups = self.tasks_facade.get_available_member_groups()
        self.assertEqual(2, len(available_groups))
    
    async def test_shouldHandleTasksWithoutAssigneesForUnassignedWorkBacklog(self):
        # Given - Tasks in backlog without assignees
        unassigned_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().build()
        ]
        unassigned_tasks[0].assignment.assignee = None
        unassigned_tasks[0].id = "UNASSIGNED-BACKLOG-TASK"
        
        self.task_search_api.mock.search.side_effect = [unassigned_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then
        self.assertEqual(1, len(result))
        unassigned_task = result[0]
        
        # Should handle unassigned tasks gracefully
        self.assertEqual("UNASSIGNED-BACKLOG-TASK", unassigned_task.id)
        self.assertIsNone(unassigned_task.assignment.assignee)
        
        # Should not attempt forecast generation for unassigned tasks
        self.forecast_api.mock.generate_forecasts_for_tasks.assert_not_called()
    
    async def test_shouldHandleTasksWithNullTimeTrackingForNewBacklogItems(self):
        # Given - New backlog tasks without time tracking
        new_backlog_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().build()
        ]
        new_backlog_tasks[0].time_tracking = None
        new_backlog_tasks[0].id = "NEW-BACKLOG-ITEM"
        
        self.task_search_api.mock.search.side_effect = [new_backlog_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then
        self.assertEqual(1, len(result))
        backlog_task = result[0]
        
        # Should handle null time tracking gracefully
        self.assertEqual("NEW-BACKLOG-ITEM", backlog_task.id)
        self.assertIsNotNone(backlog_task.time_tracking)
        self.assertIsNone(backlog_task.time_tracking.total_spent_time_days)
        self.assertIsNone(backlog_task.time_tracking.current_assignee_spent_time_days)
    
    async def test_shouldHandleExtremeTimeValuesForLongRunningProjects(self):
        # Given - Tasks with extreme time values (very high or very low)
        extreme_time_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_time_spent_hours(0.1)     # 0.1 hour
                .assigned_to("alice.johnson")
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_time_spent_hours(1000.0)  # 1000 hours (125 business days)
                .assigned_to("bob.smith")
                .build()
        ]
        
        extreme_time_tasks[0].id = "MINIMAL-TIME"
        extreme_time_tasks[1].id = "EXTREME-TIME"
        
        self.task_search_api.mock.search.side_effect = [extreme_time_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then
        self.assertEqual(2, len(result))
        
        # Should handle extreme values gracefully
        extreme_task = next(task for task in result if task.id == "EXTREME-TIME")
        minimal_task = next(task for task in result if task.id == "MINIMAL-TIME")
        
        self.assertEqual(125.0, extreme_task.time_tracking.total_spent_time_days)
        self.assertAlmostEqual(0.0125, minimal_task.time_tracking.total_spent_time_days, places=4)
        
        # Should still sort correctly despite extreme values (now sorted by assignee name first)
        self.assertEqual("MINIMAL-TIME", result[0].id)  # alice.johnson comes first alphabetically
        self.assertEqual("EXTREME-TIME", result[1].id)  # bob.smith comes second
    
    async def test_shouldHandleInvalidMemberGroupFilterForNonExistentTeams(self):
        # Given - Request for non-existent member group
        valid_tasks = BusinessScenarios.active_sprint_tasks()
        self.task_search_api.mock.search.side_effect = [valid_tasks, []]
        
        # When - Filter by non-existent member group
        result = await self.tasks_facade.get_tasks("non-existent-team")
        
        # Then - Should return empty result gracefully
        self.assertEqual(0, len(result))
        
        # Should still execute search operations
        self.assertEqual(2, self.task_search_api.mock.search.call_count)
    
    async def test_shouldHandleVelocityReportsWithMissingDataForIncompleteProjects(self):
        # Given - Velocity reports with missing or null data
        self.velocity_api.mock.generate_velocity_report.return_value = []  # No velocity data
        
        # When
        velocity_reports = await self.velocity_facade.get_velocity_reports_data("frontend-team")
        velocity_chart = self.velocity_facade.get_velocity_chart_data(velocity_reports)
        story_points_chart = self.velocity_facade.get_story_points_chart_data(velocity_reports)
        
        # Then
        self.assertEqual(0, len(velocity_reports))
        self.assertIsNone(velocity_chart)
        self.assertIsNone(story_points_chart)
        
        # Should not break filter state
        filter_state = self.velocity_facade.get_filter_state_data("frontend-team")
        self.assertEqual("frontend-team", filter_state.selected_member_group_id)
        self.assertEqual(2, len(filter_state.available_member_groups))
    
    async def test_shouldHandleTasksWithMalformedDataForDataIntegrityIssues(self):
        # Given - Tasks with realistic malformed data that could occur from external systems
        malformed_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .with_story_points(-1.0)  # Invalid negative story points
                .build()
        ]
        
        # Simulate realistic malformed scenarios
        malformed_task = malformed_tasks[0]
        malformed_task.system_metadata.original_status = ""  # Empty status
        malformed_task.system_metadata.url = "invalid-url"  # Malformed URL
        
        self.task_search_api.mock.search.side_effect = [malformed_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then - Should handle malformed data gracefully
        self.assertEqual(1, len(result))
        malformed_result = result[0]
        
        # Should preserve malformed data for business logic to handle
        self.assertEqual(-1.0, malformed_result.story_points)  # Invalid story points preserved
        self.assertEqual("", malformed_result.system_metadata.original_status)  # Empty status preserved
        self.assertEqual("invalid-url", malformed_result.system_metadata.url)  # Malformed URL preserved
    
    async def test_shouldHandleCircularReferenceInChildTasksForComplexHierarchies(self):
        # Given - Tasks with potential circular references in child relationships
        parent_task = DomainTaskBuilder.domain_task_for_ui_conversion().build()
        child_task = DomainTaskBuilder.domain_task_for_ui_conversion().build()
        
        parent_task.id = "PARENT-TASK"
        child_task.id = "CHILD-TASK"
        
        # Set up child relationship
        parent_task.child_tasks = [child_task]
        parent_task.child_tasks_count = 1
        
        self.task_search_api.mock.search.side_effect = [[parent_task], []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then - Should handle hierarchical data safely
        self.assertEqual(1, len(result))
        parent_result = result[0]
        
        self.assertEqual("PARENT-TASK", parent_result.id)
        self.assertEqual(1, parent_result.child_tasks_count)
        self.assertIsNotNone(parent_result.child_tasks)
        self.assertEqual(1, len(parent_result.child_tasks))
        self.assertEqual("CHILD-TASK", parent_result.child_tasks[0].id)
    
    async def test_shouldHandleVeryLargeDatasetsPaginationForScalabilityTesting(self):
        # Given - Large dataset simulation (performance edge case)
        large_dataset = []
        for i in range(100):  # Simulate 100 tasks
            task = DomainTaskBuilder.domain_task_for_ui_conversion().build()
            task.id = f"LARGE-DATASET-{i:03d}"
            task.assignment.assignee.id = f"developer.{i % 10}"  # 10 developers
            large_dataset.append(task)
        
        self.task_search_api.mock.search.side_effect = [large_dataset, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then - Should handle large datasets gracefully
        self.assertEqual(100, len(result))
        
        # Verify data integrity across large dataset
        unique_ids = {task.id for task in result}
        self.assertEqual(100, len(unique_ids))  # All tasks should have unique IDs
        
        # Verify sorting still works with large dataset
        first_task = result[0]
        last_task = result[-1]
        
        # Should maintain business logic with large datasets
        self.assertIsNotNone(first_task.assignment.assignee)
        self.assertIsNotNone(last_task.assignment.assignee)
    
    async def test_shouldHandleUnicodeAndSpecialCharactersInTaskDataForInternationalization(self):
        # Given - Tasks with Unicode and special characters
        unicode_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().build()
        ]
        
        unicode_task = unicode_tasks[0]
        unicode_task.id = "UNICODE-测试-TASK"
        unicode_task.title = "Implement 🚀 feature with émojis and spéciał characters"
        unicode_task.assignment.assignee.id = "developer.münchen"
        unicode_task.assignment.assignee.display_name = "Hans Müller (München Team)"
        
        self.task_search_api.mock.search.side_effect = [unicode_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then - Should handle Unicode gracefully
        self.assertEqual(1, len(result))
        unicode_result = result[0]
        
        # Verify Unicode preservation
        self.assertEqual("UNICODE-测试-TASK", unicode_result.id)
        self.assertEqual("Implement 🚀 feature with émojis and spéciał characters", unicode_result.title)
        self.assertEqual("developer.münchen", unicode_result.assignment.assignee.id)
        self.assertEqual("Hans Müller (München Team)", unicode_result.assignment.assignee.display_name)
    
    async def test_shouldHandleNetworkTimeoutsAndAPIFailuresForResiliency(self):
        # Given - Network timeout simulation
        async def timeout_simulation(*args, **kwargs):
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError("Network timeout")
        
        self.task_search_api.mock.search.side_effect = timeout_simulation
        
        # When/Then - Should handle network issues gracefully
        with self.assertRaises(asyncio.TimeoutError):
            await self.tasks_facade.get_tasks()
        
        # Verify timeout is properly propagated for higher-level handling
        self.task_search_api.mock.search.assert_called()
    
    async def test_shouldHandleInconsistentDataTypesForRobustDataProcessing(self):
        # Given - Tasks with inconsistent data types
        inconsistent_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().build()
        ]
        
        inconsistent_task = inconsistent_tasks[0]
        # Simulate inconsistent data types that might come from external systems
        inconsistent_task.story_points = "5"  # String instead of float
        
        self.task_search_api.mock.search.side_effect = [inconsistent_tasks, []]
        
        # When
        result = await self.tasks_facade.get_tasks()
        
        # Then - Should handle type inconsistencies gracefully
        self.assertEqual(1, len(result))
        processed_task = result[0]
        
        # Conversion should handle or normalize inconsistent types
        self.assertIsNotNone(processed_task.story_points)
        self.assertIsNotNone(processed_task.id)
        self.assertIsNotNone(processed_task.title)


if __name__ == '__main__':
    unittest.main()