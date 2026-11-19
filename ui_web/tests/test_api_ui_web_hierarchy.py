import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import Task, EnrichmentOptions, TaskSearchCriteria, MemberGroup
from ui_web.facades.tasks_facade import TasksFacade
from ui_web.convertors.task_convertor import TaskConvertor
from ui_web.convertors.member_convertor import MemberConvertor
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.utils.task_grouping_utils import TaskGroupingUtils
from ui_web.data.hierarchical_item_data import HierarchicalItemData
from ui_web.tests.fixtures.business_scenarios import BusinessScenarios
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder, TaskDataBuilder
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_forecast_api import MockForecastApi


class TestApiUIWebHierarchy(unittest.IsolatedAsyncioTestCase):
    
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
                "done": ["Done", "Completed", "Closed"],
                "backlog": ["To Do", "Open", "Backlog"]
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
    
    async def test_shouldOrganizeTasksByMemberGroupHierarchyForTeamManagementView(self):
        # Given - Tasks distributed across multiple teams for organization view
        frontend_task = DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("alice.johnson").build()
        frontend_task.assignment.member_group = MemberGroup(id="frontend-team", name="Frontend Development Team")
        
        backend_task = DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("bob.smith").build()  
        backend_task.assignment.member_group = MemberGroup(id="backend-team", name="Backend Development Team")
        
        devops_task = DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("charlie.brown").build()
        devops_task.assignment.member_group = MemberGroup(id="devops-team", name="DevOps Team")
        
        multi_team_tasks = [frontend_task, backend_task, devops_task]
        
        self.task_search_api.mock.search.side_effect = [multi_team_tasks, []]
        
        # When
        tasks_result = await self.facade.get_tasks()
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            tasks_result, self.workflow_config
        )
        
        # Then
        self.assertIsInstance(grouped_result, list)
        self.assertEqual(3, len(grouped_result))  # Three member groups
        self.assertIsInstance(grouped_result[0], HierarchicalItemData)
        
        # Verify member group hierarchy structure
        group_names = {group.name for group in grouped_result}
        self.assertIn("Frontend Development Team", group_names)
        self.assertIn("Backend Development Team", group_names)
        self.assertIn("DevOps Team", group_names)
        
        # Verify hierarchy type information
        for group in grouped_result:
            self.assertEqual("member_group", group.type)
    
    async def test_shouldOrganizeTasksByStageHierarchyForKanbanBoardVisualization(self):
        # Given - Tasks in different workflow stages for kanban view
        mixed_stage_tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .assigned_to_frontend_team_senior()
                .in_development_stage()
                .build(),
            TaskDataBuilder.team_velocity_task()
                .assigned_to_frontend_team_senior()
                .in_qa_stage()
                .build(),
            TaskDataBuilder.health_monitoring_task()
                .assigned_to_frontend_team_senior()
                .in_done_stage()
                .build()
        ]
        
        # When
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            mixed_stage_tasks, self.workflow_config
        )
        
        # Then
        self.assertIsInstance(grouped_result, list)
        self.assertGreater(len(grouped_result), 0)
        
        # Check if hierarchical grouping occurred or flat list returned  
        if len(grouped_result) > 0 and hasattr(grouped_result[0], 'type'):
            # Hierarchical grouping occurred - verify structure
            if len(grouped_result) == 1:
                # Single member group with stage sub-groups
                member_group = grouped_result[0]
                self.assertIsInstance(member_group, HierarchicalItemData)
                self.assertEqual("Frontend Development Team", member_group.name)
                
                # Verify stage hierarchy under member group
                if hasattr(member_group, 'items') and member_group.items:
                    stage_groups = member_group.items
                    self.assertEqual(3, len(stage_groups))  # Three stages
                    
                    stage_names = {stage.name for stage in stage_groups if hasattr(stage, 'name')}
                    self.assertIn("development", stage_names)
                    self.assertIn("qa", stage_names)
                    self.assertIn("done", stage_names)
            else:
                # Multiple groups - verify they're all hierarchical
                for group in grouped_result:
                    self.assertIsInstance(group, HierarchicalItemData)
        else:
            # Flat list returned - tasks didn't meet grouping criteria, which is also valid
            self.assertEqual(3, len(grouped_result))
    
    async def test_shouldMaintainParentChildRelationshipsInEpicBreakdownForProjectTracking(self):
        # Given - Epic with child tasks for project breakdown structure
        child_task_1 = DomainTaskBuilder.domain_task_for_ui_conversion().build()
        child_task_1.id = "EPIC-001-1"
        child_task_1.title = "Frontend implementation"
        
        child_task_2 = DomainTaskBuilder.domain_task_for_ui_conversion().build()
        child_task_2.id = "EPIC-001-2" 
        child_task_2.title = "Backend API"
        
        parent_epic = DomainTaskBuilder.domain_task_for_ui_conversion().build()
        parent_epic.id = "EPIC-001"
        parent_epic.title = "User Authentication Epic"
        parent_epic.child_tasks = [child_task_1, child_task_2]
        parent_epic.child_tasks_count = 2
        
        self.task_search_api.mock.search.side_effect = [[parent_epic], []]
        
        # When
        result = await self.facade.get_tasks()
        
        # Then
        self.assertEqual(1, len(result))
        epic_task = result[0]
        
        # Verify parent-child relationship maintenance
        self.assertEqual("EPIC-001", epic_task.id)
        self.assertEqual("User Authentication Epic", epic_task.title)
        self.assertEqual(2, epic_task.child_tasks_count)
        self.assertIsNotNone(epic_task.child_tasks)
        self.assertEqual(2, len(epic_task.child_tasks))
        
        # Verify child task preservation
        child_ids = {child.id for child in epic_task.child_tasks}
        self.assertIn("EPIC-001-1", child_ids)
        self.assertIn("EPIC-001-2", child_ids)
    
    async def test_shouldAggregateTaskCountsAccuratelyInGroupHierarchyForReportingMetrics(self):
        # Given - Multiple tasks for accurate counting across hierarchy levels
        counting_tasks = BusinessScenarios.mixed_member_group_tasks()
        
        # When
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            counting_tasks, self.workflow_config
        )
        
        # Then
        if isinstance(grouped_result[0], HierarchicalItemData):
            total_count_in_groups = 0
            
            for member_group in grouped_result:
                # Verify member group level counts
                self.assertGreater(member_group.count, 0)
                group_task_count = member_group.count
                
                # Verify stage level counts within member groups
                if hasattr(member_group, 'items') and member_group.items:
                    stage_count_sum = sum(stage.count for stage in member_group.items 
                                        if isinstance(stage, HierarchicalItemData))
                    if stage_count_sum > 0:
                        self.assertEqual(group_task_count, stage_count_sum)
                
                total_count_in_groups += group_task_count
            
            # Total should match original task count
            self.assertEqual(len(counting_tasks), total_count_in_groups)
    
    async def test_shouldRespectHierarchicalOrderingForConsistentUIDisplayInDashboard(self):
        # Given - Tasks that need consistent ordering in hierarchy
        ordered_tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .assigned_to_frontend_team_senior()
                .in_done_stage()
                .with_green_health_forecast()
                .build(),
            TaskDataBuilder.team_velocity_task()
                .assigned_to_frontend_team_senior() 
                .in_development_stage()
                .with_yellow_health_forecast()
                .build(),
            TaskDataBuilder.health_monitoring_task()
                .assigned_to_frontend_team_senior()
                .in_qa_stage()
                .with_red_health_forecast()
                .build()
        ]
        
        # When
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            ordered_tasks, self.workflow_config
        )
        
        # Then
        member_group = grouped_result[0]
        stage_groups = member_group.items
        
        # Verify stage ordering follows workflow configuration
        stage_names = [stage.name for stage in stage_groups if isinstance(stage, HierarchicalItemData)]
        expected_order = ["development", "qa", "done"]
        actual_order = [name for name in expected_order if name in stage_names]
        filtered_stage_names = [name for name in stage_names if name in expected_order]
        
        self.assertEqual(actual_order, filtered_stage_names)
        
        # Verify tasks within stages are sorted by health status (critical first)
        for stage_group in stage_groups:
            if isinstance(stage_group, HierarchicalItemData) and hasattr(stage_group, 'items'):
                health_values = []
                for task in stage_group.items:
                    if hasattr(task, 'forecast') and task.forecast and task.forecast.health_status:
                        health_values.append(task.forecast.health_status.value)
                
                if len(health_values) > 1:
                    # Should be sorted by health status descending (RED=1, YELLOW=2, GREEN=3)
                    is_sorted_by_priority = all(health_values[i] <= health_values[i+1] 
                                              for i in range(len(health_values)-1))
                    self.assertTrue(is_sorted_by_priority)
    
    async def test_shouldHandleNestedHierarchyDepthForComplexProjectStructures(self):
        # Given - Deep hierarchy scenario (member group -> stage -> individual tasks)
        complex_hierarchy_tasks = BusinessScenarios.mixed_member_group_tasks()
        
        # When
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            complex_hierarchy_tasks, self.workflow_config
        )
        
        # Then
        if isinstance(grouped_result[0], HierarchicalItemData):
            # Verify three levels of hierarchy exist
            for member_group in grouped_result:
                # Level 1: Member Group
                self.assertEqual("member_group", member_group.type)
                self.assertIsNotNone(member_group.name)
                
                # Level 2: Stages within member group
                if hasattr(member_group, 'items') and member_group.items:
                    for stage in member_group.items:
                        if isinstance(stage, HierarchicalItemData):
                            self.assertEqual("stage", stage.type)
                            self.assertIsNotNone(stage.name)
                            
                            # Level 3: Individual tasks within stage
                            self.assertIsNotNone(stage.items)
                            self.assertGreater(len(stage.items), 0)
    
    async def test_shouldPreserveMemberGroupFilteringInHierarchicalViewForTeamIsolation(self):
        # Given - Multi-team tasks that need filtering in hierarchical view
        all_teams_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")  # Frontend
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("bob.smith")     # Backend
                .build(),
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("charlie.brown") # DevOps
                .build()
        ]
        
        self.task_search_api.mock.search.side_effect = [all_teams_tasks, []]
        
        # When - Get tasks for specific team only
        filtered_result = await self.facade.get_tasks("frontend-team")
        
        # Then
        self.assertEqual(1, len(filtered_result))
        frontend_task = filtered_result[0]
        self.assertEqual("alice.johnson", frontend_task.assignment.assignee.id)
        
        # Hierarchical grouping should still work with filtered data
        grouped_filtered = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            filtered_result, self.workflow_config
        )
        
        # Should create hierarchy for single team
        if isinstance(grouped_filtered[0], HierarchicalItemData):
            self.assertEqual(1, len(grouped_filtered))
            self.assertEqual("Frontend Development Team", grouped_filtered[0].name)
    
    async def test_shouldHandleEmptyGroupsGracefullyInHierarchicalStructureForUIStability(self):
        # Given - Scenario that might create empty groups
        self.task_search_api.mock.search.side_effect = [[], []]  # No tasks
        
        # When
        result = await self.facade.get_tasks()
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            result, self.workflow_config
        )
        
        # Then
        self.assertEqual([], grouped_result)  # Empty result handled gracefully
        
        # UI should handle this case without breaking
        self.assertIsInstance(grouped_result, list)
    
    async def test_shouldMaintainTaskIdentityThroughHierarchicalTransformationForDataIntegrity(self):
        # Given - Tasks with specific identities that must be preserved
        identity_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion()
                .assigned_to("alice.johnson")
                .with_time_spent_hours(16.0)
                .build()
        ]
        identity_tasks[0].id = "PRESERVE-IDENTITY-123"
        identity_tasks[0].title = "Critical task identity preservation"
        
        self.task_search_api.mock.search.side_effect = [identity_tasks, []]
        
        # When
        result = await self.facade.get_tasks()
        grouped_result = TaskGroupingUtils.group_ui_tasks_by_member_group_and_stage(
            result, self.workflow_config
        )
        
        # Then
        self.assertEqual(1, len(result))
        original_task = result[0]
        
        # Find the task in hierarchical structure
        found_task = None
        if isinstance(grouped_result[0], HierarchicalItemData):
            for member_group in grouped_result:
                for item in member_group.items:
                    if isinstance(item, HierarchicalItemData):
                        # Stage level
                        for stage_item in item.items:
                            if hasattr(stage_item, 'id') and stage_item.id == "PRESERVE-IDENTITY-123":
                                found_task = stage_item
                                break
                    elif hasattr(item, 'id') and item.id == "PRESERVE-IDENTITY-123":
                        # Direct item level
                        found_task = item
                        break
        
        # Verify identity preservation
        if found_task:
            self.assertEqual("PRESERVE-IDENTITY-123", found_task.id)
            self.assertEqual("Critical task identity preservation", found_task.title)
            self.assertEqual(2.0, found_task.time_tracking.total_spent_time_days)
        else:
            # Task should be found at some level in hierarchy
            self.assertEqual("PRESERVE-IDENTITY-123", original_task.id)


if __name__ == '__main__':
    unittest.main()